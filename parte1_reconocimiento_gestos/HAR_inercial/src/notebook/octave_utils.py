import numpy as np
from oct2py import octave

def FeatureExtraction(AccX_array, AccY_array, AccZ_array, window_size=200, overlap=150, debug=False):
    """
    Extract MFCC (x10 x3axis) and functionals (mean & std) features from a sample of the 3D acceleromenter.

      :param AccX_array: Array with all the timesteps tht we have for the X component of the acceleromenter signal. (200 timesteps in our case)
      :param AccY_array: Array with all the timesteps tht we have for the Y component of the acceleromenter signal. (200 timesteps in our case)
      :param AccZ_array: Array with all the timesteps tht we have for the Z component of the acceleromenter signal. (200 timesteps in our case)
      :param window_size: Size of the window to apply to the raw signals (in number of samples). Default value in our case: 150 samples = 3 seconds (150 samples/50samplespsec)
      :param overlap: Overlap to apply between windows (in number of samples).  Default value in our case: 100 samples = 2 seconds (100 samples/50samplespsec)
    """
    aux_AccX_array = AccX_array[np.newaxis, :].T
    aux_AccY_array = AccY_array[np.newaxis, :].T
    aux_AccZ_array = AccZ_array[np.newaxis, :].T
    mfcc_plp = octave.calcula_features_mfcc_plp_online_new(aux_AccX_array, aux_AccY_array, aux_AccZ_array, window_size, overlap, False)

    functionals = [np.mean(aux_AccX_array), np.mean(aux_AccY_array), np.mean(aux_AccZ_array),
                   np.std(aux_AccX_array), np.std(aux_AccY_array), np.std(aux_AccZ_array)]

    if debug:
        print("\n[FeatureExtraction]\n")
        #print(aux_AccX_array)
        #print(aux_AccY_array)
        #print(aux_AccZ_array)
        print("\n[Result FeatureExtraction]\n")
        #print(result)
        print(functionals)
    res = np.append((np.asarray(mfcc_plp, dtype=float)),(np.asarray(functionals, dtype=float)))
    return res

def GetFeatureNames():
  """
    Return a list with the names of features extracted by FeatureExtraction
  """
  name_cols = []
  for i in range(1,37):
    if(i in range(1,11)):
      feature_name = "X_MFCC_param"+str(i)
    elif(i in range(11,21)):
      feature_name = "Y_MFCC_param"+str(i)
    elif(i in range(21,31)):
      feature_name = "Z_MFCC_param"+str(i)
    elif(i in [31]):
      feature_name = "X_mean_param"
    elif(i in [32]):
      feature_name = "Y_mean_param"
    elif(i in [33]):
      feature_name = "Z_mean_param"
    elif(i in [34]):
      feature_name = "X_std_param"
    elif(i in [35]):
      feature_name = "Y_std_param"
    elif(i in [36]):
      feature_name = "Z_std_param"
    name_cols.append(feature_name)
  return name_cols