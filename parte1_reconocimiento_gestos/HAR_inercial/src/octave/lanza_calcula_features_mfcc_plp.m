printf('Calling Octave RASTAPLP ...\n');
pkg load tsa
pkg load image
pkg load statistics
%pkg load geometry
pkg load linear-algebra
pkg load signal


calcula_features_mfcc_plp('../lista_todos.lis');

printf('END\n');
