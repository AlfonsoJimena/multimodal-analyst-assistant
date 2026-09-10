import weka.core.jvm as jvm
from weka.core.converters import Loader, Saver
from weka.core.dataset import Instances
from weka.classifiers import Classifier, Evaluation
from weka.core.dataset import Instance
import weka.core.serialization as serialization

def InitNewDataset(dataset_file):
    """
    """
    print("\n[InitNewDataset]\n\t[input file = " + dataset_file + "]\n")
    aux_dataset = LoadDataset(dataset_file)
    sample_instance = aux_dataset.get_instance(0)
    new_dataset = aux_dataset
    new_dataset.delete()
    return [new_dataset, sample_instance]

def LoadDataset(dataset_file, debug = False):
    """
    Load a dataset in a Weka known format and return it. The input dataset must have the class as the last attribute.
      :param dataset_file: Path to the input dataset in ARFF format.
    """
    if debug:
       print("\n[LoadDataset]\ninput file = " + dataset_file + "\n")
    loader = Loader("weka.core.converters.ArffLoader")
    dataset = loader.load_file(dataset_file)
    dataset.class_is_last()

    return dataset

def LoadDatasetAsCSV(dataset_file, debug = False):
    """
    Load a dataset in a Weka known format and return it. The input dataset must have the class as the last attribute.
      :param dataset_file: Path to the input dataset in CSV format.
    """
    if debug:
       print("\n[LoadDataset]\ninput file = " + dataset_file + "\n")
    loader = Loader("weka.core.converters.CSVLoader")
    dataset = loader.load_file(dataset_file)
    dataset.class_is_last()
    return dataset


def CreateClassifier(classname="weka.classifiers.trees.J48", options=["-C", "0.25"]):
  """
    Create a new mode/classifier usig Weka.
      :param classname: This param receive the package in which the algorithm is, as it appears in Weka API. (https://weka.sourceforge.io/doc.stable/)
      :param options: List with the opcions that the algorithm accepts. This options vary with the algorithm, check Weka API for more information about
      the options that each algorithm has.
  """
  model = Classifier(classname=classname, options=options)
  return model

def LoadClassifier(classifier_file, debug=False):
    """
      Load a classifier from its saved archive ***.model .
      :param classifier_file: Path where we have the classifier saved: e.g. J48_trained_model.model
    """
    if debug:
        print("\n[LoadClassifier][" + classifier_file + "]\n")
    # read classifier object
    model = Classifier(jobject=serialization.read(classifier_file))
    print(model)
    return model

def TrainModel(train_dataset, classifier, output_path_model):
    """
      Train a built model.
      :param train_dataset: Dataset loaded in Weka format (see LoadDatasetAsCSV or LoadDataset).
      :param classifier: Classifier built or created (see CreateClassifier)
      :param output_path_model: Path where we want to save our model. e.g. "J48_trained_model.model"
    """
    #Indicate where is class label
    train_dataset.class_is_last()

    # train classifier
    classifier.build_classifier(train_dataset)

    # save classifier object
    print("\n[TrainedModel]\n\n")
    print(classifier)
    serialization.write(output_path_model, classifier)
    return classifier

def EvalClassifier(trained_classifier, train_dataset, test_dataset):
    """
      Eval a trained model.
      :param trained_classifier: Classifier built and trained(see TrainModel)
      :param train_dataset: Dataset loaded in Weka format with training data (see LoadDatasetAsCSV or LoadDataset).
      :param test_dataset: Dataset loaded in Weka format with data to test (see LoadDatasetAsCSV or LoadDataset).
    """
    evl_train = Evaluation(train_dataset)
    evl_test = Evaluation(train_dataset)
    print("--------RESULTS IN TRAINING----------")
    evl_train.test_model(trained_classifier, train_dataset)
    print(evl_train.summary())
    print("--------RESULTS IN TEST----------")
    evl_test.test_model(trained_classifier, test_dataset)
    print(evl_test.summary())
    eval_accuracy = evl_test.percent_correct
    return eval_accuracy

def Recognize(trained_classifier,test_dataset):
    """
      Make predictions of full dataset and print information of each sample results.
      :param trained_classifier: Classifier built and trained(see TrainModel)
      :param test_dataset: Dataset loaded in Weka format with data to test (see LoadDatasetAsCSV or LoadDataset).
    """
    print("# - actual - predicted - error - class distribution")
    for index, inst in enumerate(test_dataset):
      pred = trained_classifier.classify_instance(inst)
      dist = trained_classifier.distribution_for_instance(inst)
      print("%d - %s - %s - %s  - %s" %
                (index+1,
                inst.get_string_value(inst.class_index),
                inst.class_attribute.value(int(pred)),
                "yes" if pred != inst.get_value(inst.class_index) else "no",
                str(dist.tolist())))
