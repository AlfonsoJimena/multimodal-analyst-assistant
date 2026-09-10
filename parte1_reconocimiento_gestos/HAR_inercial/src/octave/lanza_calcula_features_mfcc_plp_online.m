printf('Calling Octave RASTAPLP ...\n');
%pkg load tsa
%pkg load image
%pkg load statistics
%%pkg load geometry
%pkg load linear-algebra
%pkg load signal

addpath(genpath("/home/pi/H_SMARTPHONE_WATCH_FFM_LITE/scripts/octave/"));

load_octave_packages();

filename = './demoAccelerometerSample_1s_stand.csv';
M = csvread(filename);

%calcula_features_mfcc_plp_online(M(:,1),M(:,2),M(:,3));
calcula_features_mfcc_plp_online(M(1:200,1),M(1:200,2),M(1:200,3));

printf('END\n');
