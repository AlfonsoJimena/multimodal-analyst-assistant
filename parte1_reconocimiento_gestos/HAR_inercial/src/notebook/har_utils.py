import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from scipy.io import arff

def Download_arff(link):
  data=arff.loadarff(link)
  df_data=pd.DataFrame(data = data[0], columns={''})
  return df_data

# Load CSV data
def DownloadDS(filename, csv_with_user_info=False):
  df_csv = pd.read_csv(filename, sep=",", header=0)

  if csv_with_user_info:
    col_names = ['param' + str(i) for i in range(1,601)]
    col_names = col_names + ['class', 'user']
  else:
    col_names = ['param' + str(i) for i in range(1,601)]
    col_names = col_names + ['class']

  df_csv.columns = col_names
  return df_csv

# Load CSV data
# (two CSV: train and test)
def DownloadDS_train_test(path_train, path_test):
  df_train_csv = pd.read_csv(path_train, sep=",", header=0)
  df_test_csv = pd.read_csv(path_test, sep=",", header=0)

  col_names = ["param"+str(i) for i in range(1,601)]
  col_names = col_names + ["class", "user"]

  df_train_csv.columns = col_names
  df_test_csv.columns = col_names

  print('[INPUT DATA FROM][%s][SUCCESSFULLY LOADED!!!]' % path_train)
  print('[INPUT DATA FROM][%s][SUCCESSFULLY LOADED!!!]' % path_test)
  return df_train_csv, df_test_csv

def load_dataset(filepath, csv_with_user_info=False, percentage_test_split=0.2):
    """
    Loads a dataset from a CSV file and splits it into training and testing sets.
    
    Args:
        filepath (str): Path to the CSV file.
        csv_with_user_info (bool): Whether the CSV contains user information.
        percentage_test_split (float): Percentage of data to use for testing.
        
    Returns:
        X_train, X_test, y_train, y_test, df_train, df_test
    """
    df_csv = pd.read_csv(filepath, sep=",", header=0)

    if csv_with_user_info:
        # Adjust column names if necessary based on your specific CSV structure
        col_names = ['param' + str(i) for i in range(1, 601)] + ['class', 'user']
    else:
        col_names = ['param' + str(i) for i in range(1, 601)] + ['class']
    
    df_csv.columns = col_names

    if csv_with_user_info:
        X = df_csv.drop(['class', 'user'], axis=1)
    else:
        X = df_csv.drop(['class'], axis=1)
    
    y = df_csv['class']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=percentage_test_split, random_state=42
    )
    
    df_train = pd.concat([X_train, y_train], axis=1).reset_index(drop=True)
    df_test = pd.concat([X_test, y_test], axis=1).reset_index(drop=True)

    return X_train, X_test, y_train, y_test, df_train, df_test

def load_arff(link):
    """Loads an ARFF file into a DataFrame."""
    data = arff.loadarff(link)
    return pd.DataFrame(data[0])

def get_acceleration_axis(df):
    """
    Splits the dataframe into X, Y, Z axes arrays.
    Assumes 600 parameters where 1-200 are X, 201-400 are Y, 401-600 are Z.
    """
    AccX = df.loc[:, 'param1':'param200']
    AccY = df.loc[:, 'param201':'param400']
    AccZ = df.loc[:, 'param401':'param600']
    AccAll = df.loc[:, 'param1':'param600']
    y = df["class"]
    return AccX, AccY, AccZ, AccAll, y

def Save_CSV_from_Df(df_in, class_mapping, output_csv_filename):
  # We start by creating a copy of the input df
  df_out = df_in.copy()

  # Convert class data from numeric to nominal
  df_out['labels'] = df_out['class'].replace(class_mapping)

  # Remove numeric class and user column
  df_out = df_out.drop(['class'], axis=1)
  if 'user' in df_out.columns:
    df_out = df_out.drop(['user'], axis=1)

  # Before saving, we first sort the DataFrame based on the 'labels' column
  df_out = df_out.sort_values(by='labels')

  # We reset the index after sorting
  df_out = df_out.reset_index(drop=True)

  # Save dataframe
  df_out.to_csv(output_csv_filename, sep = ",", index=False, header=True, float_format=f'%.8f')

def CalculateCI(num_samples, accuracy):
  """
    Calculate confidence interval for a confidence of 95%
    :param num_samples: Number of samples for the set to evaluate
    :param accuracy: Accuracy of the model
  """
  return 1.96*(np.sqrt(((100-accuracy)*(accuracy))/num_samples))
