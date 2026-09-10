import sys
import os

# We add the common folder to the path
# This folder contains the libraries that are shared between the different demos
# This way we can import them without duplicating code
lib_path = os.path.abspath("../common/")
sys.path.append(lib_path)

from gui import wait_for_keypress
import random

# Configuration class for the dataset generation
class Config:
    def __init__(self, 
                 classes=None, 
                 dataset_dir='./data/new_dataset/', 
                 num_images_per_class=100, 
                 training_percentage=66, 
                 save_images=False):
        
        # Array of class names
        self.classes = classes if classes is not None else ["gesture1", "gesture2", "gesture3"]
        self.num_classes = len(self.classes)

        # Base directory where the new dataset is going to be stored
        self.dataset_dir = dataset_dir

        # Total number of images per class in the dataset
        self.num_images_per_class = num_images_per_class

        # Percentage of the recorded images that will be used for training (rest for val)
        self.training_percentage = training_percentage

        # Flag to save images with landmarks
        self.save_images = save_images
    
    def CreateDefaultDatasetFolders(self):
        yes_to_all_result = False
        
        # Create default dataset folders
        for c in self.classes:
            new_dir = os.path.join(self.dataset_dir, "train", c)
            try:
                os.makedirs(new_dir)
            except:
                print('\n[WARNING]\n')
                print('The following directory ALREADY EXISTS!!!!')
                print(new_dir)
                print('\n[WARNING]\n')
                
                if not yes_to_all_result:
                    yes_to_all_result = wait_for_keypress('c', 'q', 'y')
            
            new_dir = os.path.join(self.dataset_dir, "val", c)
            try:
                os.makedirs(new_dir)
            except:
                print('\n[WARNING]\n')
                print('The following directory ALREADY EXISTS!!!!')
                print(new_dir)
                print('\n[WARNING]\n')
                
                if not yes_to_all_result:
                    yes_to_all_result = wait_for_keypress('c', 'q', 'y')

def RecordingSetup(config):
    num_samples_per_class = {}
    num_samples_per_class['train'] = int(config.num_images_per_class * config.training_percentage/100)
    num_samples_per_class['val']  = config.num_images_per_class - num_samples_per_class['train']
    num_samples_per_class['total'] = config.num_images_per_class

    print('\n[NEW DATASET RECORDING]')
    print('\t- %d classes: ' % config.num_classes, config.classes)
    print('\t- %d samples per class (%d samples in TOTAL)' % 
          (num_samples_per_class['total'], 
           config.num_classes * num_samples_per_class['total']))
    print('\t- %d samples for training (i.e. %0.2f%%) and %d for testing (i.e. %0.2f%%)' % 
          (num_samples_per_class['train'], 
           config.training_percentage, 
           num_samples_per_class['val'], 
           100-config.training_percentage))
    return num_samples_per_class
