import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn import decomposition
from sklearn import datasets

# LABEL FUNCTIONS

def get_class(num_classes):
  """
  name (string) the numeric classes of the data
  """
  classes_list = []
  for i in range(num_classes):
      new_class = input(f"Please, input the name of the class {i+1}: ")
      classes_list.append(new_class)
  return classes_list


def create_class_mapping(class_names):
  """
  create dictionary classes
  """
  class_mapping = {}
  for i, class_name in enumerate(class_names):
      class_mapping[i+1] = class_name
  return class_mapping

def Convert2nominal_activities(class_number, class_mapping):
  """
  mapping classes
  """
  if class_number in class_mapping:
      return class_mapping[class_number]
  else:
      return "UNK"


# def Convert2nominal_pingPong(class_number):
#   """
#     Transform numerical class to nominal classes
#     :param class_number: Number of class in numeric format
#     :return: Class as string (nominal type)
#   """
#   if(class_number == 1):
#     return "DRIVE"
#   elif(class_number == 2):
#     return "BACKHAND"
#   elif(class_number == 3):
#     return "SERVE"
#   elif(class_number == 4):
#     return "LOB"
#   else:
#     return "UNK"

def GetAccelerationAxis(df_csv):
  """
    Get arrays of X,Y and Z axis, as well as the class attribute and an array with all the parameters of the 3 axis.
    :param df_csv: Dataframe with the initial 600 parameters (or raw samples)
  """
  AccX_array = df_csv.loc[:, 'param1':'param200']
  AccY_array = df_csv.loc[:, 'param201':'param400']
  AccZ_array = df_csv.loc[:, 'param401':'param600']
  AccAll_array = df_csv.loc[:, 'param1':'param600']
  y = df_csv["class"]
  return AccX_array, AccY_array, AccZ_array, AccAll_array, y


# PLOT FUNCTIONS:

# SIMPLE PLOT PER SAMPLES
def plot_sample(sample2plot, df_csv, class_mapping):
  """
    Plot X,Y,Z raw samples of the acceleration.
    X axis is painted in red, Y xis in green and Z axis in blue.
    :param sample2plot: Number of the sample to plot
    :param df_csv: Dataframe with the initial 600 parameters (or raw samples)
  """
  # PLOT SIMPLE INSTANCE VALUES
  AccX_array_train = df_csv.loc[sample2plot, 'param1':'param200']
  AccY_array_train = df_csv.loc[sample2plot, 'param201':'param400']
  AccZ_array_train = df_csv.loc[sample2plot, 'param401':'param600']
  t = np.linspace(0, 4, 200)

  fig = plt.figure(figsize=(10, 10))
  plt.plot(t, AccX_array_train, color='r', label = "X") # plotting t, a separately
  plt.plot(t, AccY_array_train, color='g', label = "Y") # plotting t, b separately
  plt.plot(t, AccZ_array_train, color='b', label = "Z") # plotting t, c separately

  # FORMAT OF PLOT
  plt.legend(loc='lower right')
  plt.ylabel('Acceleration (m/s2)')
  plt.xlabel('Time (secs.)')
  title = 'Instance: ' + str(sample2plot)

  # Check if the 'column_name' column contains integers
  is_integer_column = df_csv['class'].apply(lambda x: isinstance(x, int)).all()

  if is_integer_column:
    #print("The 'column_name' column contains only integers")
    title = title + ' - Class: ' + Convert2nominal_activities(df_csv.loc[sample2plot, 'class'], class_mapping)
  else:
    #print("The 'column_name' column contains non-integer values")
    title = title + ' - Class: ' + df_csv.loc[sample2plot, 'class']

  plt.title(title)
  plt.show()

# PCA PLOTS
def PlotPCA(pca, Acc_array, y, title=""):
  """
    Plot a compacted vision of dataset in 3 axis using 3 main principal components of Principal Components Analysis (PCA).
    :param pca: pca analysis made with training set (check: CreatePCA)
    :param Acc_array: Array from wich we want to extract the new 3-PC
    :param y: Labels of the arrat passed in Acc_array
    :param title: Title of the plot (OPTIONAL)
  """
  #Prepare figure
  fig = plt.figure(1, figsize=(10, 10))
  plt.clf()
  ax = Axes3D(fig, rect=[0, 0, .95, 1], elev=48, azim=134)
  plt.cla()

  #Extract 3 Principal Components
  principalComponents = pca.transform(Acc_array)
  principalDf = pd.DataFrame(data = principalComponents
              , columns = ['PC_1', 'PC_2', 'PC_3'])
  finalDf = pd.concat([principalDf, y], axis = 1)
  targets = [1, 2, 3, 4]
  targets_names = ["1 - DRIVE","2 - BACKHAND","3 - SERVE","4 - LOB"]
  colors = ['r', 'g', 'b', 'm']

  #Plot them
  for target, color in zip(targets,colors):
      indicesToKeep = finalDf['class'] == target
      ax.scatter(finalDf.loc[indicesToKeep, 'PC_1'],
                finalDf.loc[indicesToKeep, 'PC_2'],
                finalDf.loc[indicesToKeep, 'PC_3'],
                c = color,
                s = 50)

  ax.legend(targets_names)
  ax.grid()
  plt.title(title)
  plt.show()



def CreatePCA(train_df, test_df):
  """
    Plot a compacted vision of dataset in 3 axis using 3 main principal components of Principal Components Analysis (PCA).
    Create PCA using training dataframe and extract plots from each axis in train and test dataframes.
    :param train_df: Training Dataframe with the initial 600 parameters (or raw samples)
    :param test_df: Testing Dataframe with the initial 600 parameters (or raw samples)
  """
  #Get components of accelerometer:
  AccX_array_train, AccY_array_train, AccZ_array_train, AccAll_array_train, y_train = GetAccelerationAxis(train_df)
  AccX_array_test, AccY_array_test, AccZ_array_test, AccAll_array_test, y_test = GetAccelerationAxis(test_df)

  pca_X = decomposition.PCA(n_components=3)
  pca_X.fit(AccX_array_train)

  pca_Y = decomposition.PCA(n_components=3)
  pca_Y.fit(AccY_array_train)

  pca_Z = decomposition.PCA(n_components=3)
  pca_Z.fit(AccZ_array_train)

  pca_all = decomposition.PCA(n_components=3)
  pca_all.fit(AccAll_array_train)

  PlotPCA(pca_X, AccX_array_train, y_train, title="PCA axis X - TRAIN SET")
  PlotPCA(pca_X, AccX_array_test, y_test, title="PCA axis X - TEST SET")
  PlotPCA(pca_Y, AccY_array_train, y_train, title="PCA axis Y - TRAIN SET")
  PlotPCA(pca_Y, AccY_array_test, y_test, title="PCA axis Y - TEST SET")
  PlotPCA(pca_Z, AccZ_array_train, y_train, title="PCA axis Z - TRAIN SET")
  PlotPCA(pca_Z, AccZ_array_test, y_test, title="PCA axis Z - TEST SET")

  PlotPCA(pca_all, AccAll_array_train, y_train, title="PCA ALL axis - TRAIN SET")
  PlotPCA(pca_all, AccAll_array_test, y_test, title="PCA ALL axis - TEST SET")
