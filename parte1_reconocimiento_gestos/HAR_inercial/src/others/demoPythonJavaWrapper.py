# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# serialization.py
# Copyright (C) 2014 Fracpete (pythonwekawrapper at gmail dot com)

import os
import tempfile
import traceback
import javabridge
import weka.core.jvm as jvm
#import wekaexamples.helper as helper
from weka.core.converters import Loader
from weka.core.dataset import Instances
from weka.classifiers import Classifier
import weka.core.serialization as serialization

from oct2py import octave
octave.addpath('/home/ffm/workspace/H_SMARTPHONE_WATCH_FFM/scripts/octave/')

import csv
from collections import defaultdict

import numpy as np
from numpy import *

columns = defaultdict(list) # each value in each column is appended to a list

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
    
def main():
    """
    Just runs some example code.
    """
    print("\n[LOADING ACCELEROMETER VALUES]\n")
    #ifile = open('demoAccelerometerSample_1s_stand.csv', "rb")
    ifile = open('demoAccelerometerSample_1s_walk.csv', "rb")
    reader = csv.reader(ifile)

    for row in reader:
        for (i,v) in enumerate(row):
            columns[i].append(float(v))
    #print(columns[0])

    AccXarray = asarray(columns[0])
    AccXarray = AccXarray[np.newaxis, :].T
    AccYarray = asarray(columns[1])
    AccYarray = AccYarray[np.newaxis, :].T
    AccZarray = asarray(columns[2])
    AccZarray = AccZarray[np.newaxis, :].T

    #print(AccXarray)
    #print(AccYarray)
    #print(AccZarray)

    print("\n[EXECUTING FEATURE EXTRACTION IN OCTAVE]\n")
    octave.calcula_features_mfcc_plp_online(AccXarray,AccYarray,AccZarray)

    #test_file = "./TEST_A_P_f_demo.arff"
    test_file = "./features/online/aux_features.arff"
    print("Loading dataset: " + test_file)
    loader = Loader("weka.core.converters.ArffLoader")
    test_data = loader.load_file(test_file)
    test_data.class_is_last()
    
    # read classifier object
    classifier_file ="./models/online/P_data_mfcc_plp.model"
    
    model = Classifier(jobject=serialization.read(classifier_file))
    #objects=serialization.read_all("./P_data_mfcc_plp.model")
    #model = Classifier(jobject)
    print(model)
    #print objects

    for index, inst in enumerate(test_data):
	pred = model.classify_instance(inst)
	dist = model.distribution_for_instance(inst)
	print(
         str(index+1) + ": label index=" + str(pred) + 
         ", class distribution=" + str(dist) + 
         ", predicted=" +  inst.class_attribute.value(int(pred)) + 
         ", actual=" + inst.get_string_value(inst.class_index))

    # save classifier and dataset header (multiple objects)
    #helper.print_title("I/O: single object")
    #print("I/O: single object")
    #serialization.write_all(outfile, [classifier, Instances.template_instances(iris_data)])
    #objects = serialization.read_all(outfile)
    #objects = serialization.read_all("../models/P_data_mfcc_plp.model")
    #for i, obj in enumerate(objects):
        #helper.print_info("Object #" + str(i+1) + ":")
    #    print("Object #" + str(i+1) + ":")
    #    if javabridge.get_env().is_instance_of(obj, javabridge.get_env().find_class("weka/core/Instances")):
    #        obj = Instances(jobject=obj)
    #    elif javabridge.get_env().is_instance_of(obj, javabridge.get_env().find_class("weka/classifiers/Classifier")):
    #        obj = Classifier(jobject=obj)
    #    print(obj)


if __name__ == "__main__":
    try:
        jvm.start()
        #TrainModel()
        main()
    except Exception, e:
        print(traceback.format_exc())
    finally:
        jvm.stop()



