# -*- coding: utf-8 -*-
"""
Created on Fri Sep 29 11:04:24 2017

@author: ffm
"""
import weka.core.jvm as jvm
from weka.core.converters import Loader, Saver
from weka.core.dataset import Instances
from weka.classifiers import Classifier
from weka.core.dataset import Instance
import weka.core.serialization as serialization

from AR_modules.config.general import RASPI, debug
from AR_modules.config.general import DATA_PATH, DATA_SET

def InitNewDataset():
    #aux_dataset = LoadDataset("./features/online/aux_features_raspi.arff")
    #aux_dataset_filename = "./features/online/aux_features_raspi.arff"
    aux_dataset_filename = DATA_PATH + DATA_SET
    print("\n[InitNewDataset]\n\t[input file = " + aux_dataset_filename + "]\n")
    aux_dataset = LoadDataset(aux_dataset_filename)
    sample_instance = aux_dataset.get_instance(0)
    new_dataset = aux_dataset
    new_dataset.delete()
    return [new_dataset, sample_instance]
    
def LoadDataset(dataset_file):
    if debug:
       print("\n[LoadDataset]\ninput file = " + dataset_file + "\n")
    loader = Loader("weka.core.converters.ArffLoader")
    dataset = loader.load_file(dataset_file)
    dataset.class_is_last()
    
    return dataset
    
def LoadClassifier(classifier_file):
    if debug:
        print("\n[LoadClassifier][" + classifier_file + "]\n")

    # read classifier object    
    model = Classifier(jobject=serialization.read(classifier_file))
    
    print(model)

    return model

def LoadInstanceForTraining(dataset, sample_instance, numerical_values, p_class):
    
    inst = sample_instance
    #num_attributes = len(numerical_values);
    num_attributes = numerical_values.size;

    #print numerical_values    
    #print("%d attributes\n" % num_attributes)

    for index in range(0, num_attributes):
        #inst.set_value(index, numerical_values[0,index])
        inst.set_value(index, numerical_values.item(index))
        #print("%d - %f\n" % (index, numerical_values.item(index)))

    target_attribute = dataset.attribute_by_name("activity") 
    
    #print "target_attribute.index = " + str(target_attribute.index)
    #print "dataset.class_index = " + str(dataset.class_index)
    #print target_attribute.values
    #inst.set_value(target_attribute.index, float(target_attribute.values.index(3)))
    inst.set_value(target_attribute.index, float(p_class))

    if debug:    
        print(inst)
    
    dataset.add_instance(inst)
       
    num_instances = dataset.num_instances
    
    print("%d instances" % num_instances)

    if debug:
       print("[LoadInstanceForTraining][num_instances = " + str(num_instances) + "]")
                
    return dataset
    
def LoadInstanceForRecognition(dataset, numerical_values):
    inst = dataset.get_instance(0)

    #num_attributes = len(numerical_values);
    num_attributes = numerical_values.size;
    
    for index in range(0, num_attributes):
        #inst.set_value(index, numerical_values[0,index])
        inst.set_value(index, numerical_values.item(index))
    
    dataset.set_instance(0, inst)

    if debug:    
        print(inst)
        
    return dataset
    
def TrainModel():
    # load a dataset
    #iris_file = helper.get_data_dir() + os.sep + "iris.arff"
    train_file = "./features/TOTAL_A_P.arff"
    print("Loading dataset: " + train_file)
    loader = Loader("weka.core.converters.ArffLoader")
    train_data = loader.load_file(train_file)
    train_data.class_is_last()
    
    # train classifier
    classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier.build_classifier(train_data)
    
    # save classifier object
    print("\n[TrainModel]\n\n")
    #outfile = tempfile.gettempdir() + os.sep + "j48.model"
    outfile ="./models/online/P_data_mfcc_plp.model"
    serialization.write(outfile, classifier)
