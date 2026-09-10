% MAIN FUNCTION
function OUTPUT = calcula_features_mfcc_plp_online(AccXorig,AccYorig,AccZorig, win_size, overlap, debug)

if debug,
	printf("\n[LOADING OCTAVE PACKAGES]\n");
endif

load_octave_packages()

%[AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread (ini_file,"%f %f %f %s %s %s %s");

% Nothing
AccX=AccXorig;
AccY=AccYorig;
AccZ=AccZorig;

%win_size =150; % 3 segundos a 50 Hz
%overlap=100; % 1 segundos a 50 Hz

if debug,
	fprintf('\ncalcula_features_mfcc_plp_online\n')
	win_size
	overlap
	AccX
endif

step = win_size - overlap;

num=size(AccX);

if (num<win_size)
 return;
endif

% FEATURES ORIGINALES

tBodyAccX = AccX'(1:win_size);
for i=1:floor((columns(AccX')-win_size)/step)
    tBodyAccX = [tBodyAccX;AccX'((i*step)+1:(i*step)+win_size)]; 
 endfor 
tBodyAccY = AccY'(1:win_size);
for i=1:floor((columns(AccY')-win_size)/step)
    tBodyAccY = [tBodyAccY;AccY'((i*step)+1:(i*step)+win_size)];
 endfor  
 tBodyAccZ = AccZ'(1:win_size);
for i=1:floor((columns(AccZ')-win_size)/step)
    tBodyAccZ = [tBodyAccZ;AccZ'((i*step)+1:(i*step)+win_size)]; 
 endfor
 
  % FEATURES ORIGINALES
 
%JERK
Zeros = zeros(rows(tBodyAccX), 1); Der1 = [Zeros diff(tBodyAccX,1,2)]; Der2 = [Zeros diff(Der1,1,2)];  tBodyAccJerkX = [Zeros diff(Der2,1,2)];
Zeros = zeros(rows(tBodyAccY), 1); Der1 = [Zeros diff(tBodyAccY,1,2)]; Der2 = [Zeros diff(Der1,1,2)];  tBodyAccJerkY = [Zeros diff(Der2,1,2)];
Zeros = zeros(rows(tBodyAccZ), 1); Der1 = [Zeros diff(tBodyAccZ,1,2)]; Der2 = [Zeros diff(Der1,1,2)];  tBodyAccJerkZ = [Zeros diff(Der2,1,2)];

%MAG
tBodyAccMag = sqrt(tBodyAccX.^2+tBodyAccY.^2+tBodyAccZ.^2);
tBodyAccJerkMag =sqrt(tBodyAccJerkX.^2+tBodyAccJerkY.^2+tBodyAccJerkZ.^2);

% FFTs
FFT = abs(fft(tBodyAccX,columns(tBodyAccX),2)); fBodyAccX = FFT(:,1:columns(tBodyAccX)/2);
FFT = abs(fft(tBodyAccY,columns(tBodyAccY),2)); fBodyAccY = FFT(:,1:columns(tBodyAccY)/2);
FFT = abs(fft(tBodyAccZ,columns(tBodyAccZ),2)); fBodyAccZ = FFT(:,1:columns(tBodyAccZ)/2);
FFT = abs(fft(tBodyAccJerkX,columns(tBodyAccJerkX),2)); fBodyAccJerkX = FFT(:,1:columns(tBodyAccJerkX)/2);
FFT = abs(fft(tBodyAccJerkY,columns(tBodyAccJerkY),2)); fBodyAccJerkY = FFT(:,1:columns(tBodyAccJerkY)/2);
FFT = abs(fft(tBodyAccJerkZ,columns(tBodyAccJerkZ),2)); fBodyAccJerkZ = FFT(:,1:columns(tBodyAccJerkZ)/2);

% JERK SOBRE LOS FFTs
fBodyAccMag = sqrt(fBodyAccX.^2+fBodyAccY.^2+fBodyAccZ.^2);
fBodyAccJerkMag =sqrt(fBodyAccJerkX.^2+fBodyAccJerkY.^2+fBodyAccJerkZ.^2);

% PARA LOS ANGLES
tBodyAccMean=(tBodyAccX+tBodyAccY+tBodyAccZ)/3;
tBodyAccJerkMean=(tBodyAccJerkX+tBodyAccJerkY+tBodyAccJerkZ)/3;

% CALCULAMOS ESTAD�STICOS DE CADA SE�AL Y CONCATENAMOS: 290 FEATURES -> 335 features

%OUTPUT = tfeatures3D(tBodyAccX,tBodyAccY,tBodyAccZ);  % 40 features
%OUTPUT = [OUTPUT tfeatures3D(tBodyAccJerkX,tBodyAccJerkY,tBodyAccJerkZ)]; %40 features

%OUTPUT = [OUTPUT tfeatures1D(tBodyAccMag)]; %13 features
%OUTPUT = [OUTPUT tfeatures1D(tBodyAccJerkMag)]; %13 features

%OUTPUT = [OUTPUT ffeatures3D(fBodyAccX,fBodyAccY,fBodyAccZ)]; %79 features
%OUTPUT = [OUTPUT ffeatures3D(fBodyAccJerkX,fBodyAccJerkY,fBodyAccJerkZ)]; %79 features

%OUTPUT = [OUTPUT ffeatures1D(fBodyAccMag)]; %13 features
%OUTPUT = [OUTPUT ffeatures1D(fBodyAccJerkMag)]; %13 features


%OUTPUT = frastaplp3D(AccX',AccY',AccZ');  %30 features
%OUTPUT = [OUTPUT fmfcc3D(AccX',AccY',AccZ')];  %30 features
OUTPUT = frastaplp3D(AccX',AccY',AccZ', win_size, step);  %30 features
OUTPUT = [OUTPUT fmfcc3D(AccX',AccY',AccZ', win_size, step)];  %30 features
OUTPUT = [OUTPUT mean(AccX) mean(AccY) mean(AccZ) std(AccX) std(AccY) std(AccZ)];  %6 features


% IMPRESI�N FINAL 
%user_mode=user(1:rows(OUTPUT));      
%model_mode=model(1:rows(OUTPUT));      
%device_mode=device(1:rows(OUTPUT));      
%activity_mode=activity(1:rows(OUTPUT));
%for i=0:rows(OUTPUT)-1           
%    user_mode(i+1)=user((i+1)*step);
%    model_mode(i+1)=model((i+1)*step);
%    device_mode(i+1)=device((i+1)*step);
%    activity_mode(i+1)=activity((i+1)*step);
%endfor 

% NO TIENE SENTIDO APLICAR ESTE TIPO DE NORMALIZACION CUANDO EL CONJUNTO DE MUESTRAS ES TAN REDUCIDO
%mean_factor = mean(OUTPUT);
%std_factor = std(OUTPUT);
%OUTPUT2 =  OUTPUT-mean(OUTPUT);
%OUTPUT2 =  (OUTPUT-mean(OUTPUT))./(std(OUTPUT));
%OUTPUT = OUTPUT2;

for i=1:rows(OUTPUT)    
  for j=1:columns(OUTPUT)  
    if (isnan(OUTPUT(i,j)))
      OUTPUT(i,j)=0;
    endif
    if (isinf(OUTPUT(i,j)))
      OUTPUT(i,j)=0;
    endif
  endfor 
endfor 

output_file = './features/online/aux_features.arff';
%[data_file ext]=strtok(ini_file,".");
%data_file2=strcat(data_file,'.arff');  
%csvwrite(data_file,user_mode);
%fid = fopen (data_file2, "w");
fid = fopen (output_file, "w");

%fid2 = fopen ("cabecera.arff", "w");
% Nombres
%fprintf(fid2, "@relation %s\n\n", data_file);
if fid < 0
  printf('\n[PROBLEMS!!!][COULD NOT OPEN %s!!!]\n', output_file);
else
  fprintf(fid, "@relation %s\n\n", output_file);
  for j=1:columns(OUTPUT)            
    %fprintf(fid2,"@attribute %d numeric\n",j);
    fprintf(fid,"@attribute %d numeric\n",j);
  endfor 
  %    fprintf(fid2,"user,model,device,activity\n");
  %fprintf(fid2,"@attribute activity {stand,sit,walk,stairsdown,stairsup,bike}\n\n@data\n");
  fprintf(fid,"@attribute activity {stand,sit,walk,stairsdown,stairsup,bike}\n\n@data\n");
  %fclose (fid2);
  
  for i=0:rows(OUTPUT)-1
  %  if (strcmp(activity_mode(i+1), "null")==1) 
  %    continue;
  %  endif
    for j=1:columns(OUTPUT)
      fprintf(fid,"%f,", OUTPUT(i+1,j));        
    endfor
    %fprintf(fid,"%s,",char(user_mode(i+1)));fprintf(fid,"%s,",char(model_mode(i+1)));fprintf(fid,"%s,",char(device_mode(i+1)));fprintf(fid,"%s\n",char(activity_mode(i+1)));
    %fprintf(fid,"%s\n", char(activity_mode(i+1)));
    fprintf(fid,"%s\n", 'stand'); % PONEMOS stand POR DEFECTO
  endfor 

  fclose (fid);
endif

endfunction




%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output3D = frastaplp3D(x,y,z)
%
% 20x3 features
%function foutputRASTAPLP3D = frastaplp3D(x,y,z)
function foutputRASTAPLP3D = frastaplp3D(x,y,z, win_size, step)

sr=8000;
rasta=0;


%fprintf('\nfrastaplp3D\n')
%win_size
%step

datax=x';
%[mm, spec] = rastaplp(datax, sr, rasta, 9);
[mm, spec] = rastaplp(datax, sr, rasta, 9, win_size, step);
foutputRASTAPLP3D = mm';

datay=y';
%[mm, spec] = rastaplp(datay, sr, rasta, 9);
[mm, spec] = rastaplp(datay, sr, rasta, 9, win_size, step);
foutputRASTAPLP3D = [foutputRASTAPLP3D mm'];

dataz=z';
%[mm, spec] = rastaplp(dataz, sr, rasta, 9);
[mm, spec] = rastaplp(dataz, sr, rasta, 9, win_size, step);
foutputRASTAPLP3D = [foutputRASTAPLP3D mm'];


endfunction



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output3D = fmfcc3D(x,y,z)
%
% 20x3 features
%function foutputMFCC3D = fmfcc3D(x,y,z)
function foutputMFCC3D = fmfcc3D(x,y,z, win_size, step)

sr=8000;
num_cep=10;
num_bands=40;


%fprintf('\nfmfcc3D\n')
wintime=double(win_size)/double(sr);
steptime=double(step)/double(sr);

datax= x';
%[mm,aspc] = melfcc(datax, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
[mm,aspc] = melfcc(datax, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, ...
  'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime',wintime, 'hoptime', steptime, ...
  'preemph', 0, 'dither', 0);
foutputMFCC3D = mm';

datay= y';
%[mm,aspc] = melfcc(datay, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
[mm,aspc] = melfcc(datay, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, ...
  'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', wintime, 'hoptime', steptime, ...
  'preemph', 0, 'dither', 0);
foutputMFCC3D = [foutputMFCC3D mm'];

dataz= z';
%[mm,aspc] = melfcc(dataz, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
[mm,aspc] = melfcc(dataz, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, ...
  'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', wintime, 'hoptime', steptime, ...
  'preemph', 0, 'dither', 0);
foutputMFCC3D = [foutputMFCC3D mm'];

endfunction



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% function output3D = tECDF(x,y,z)
%
% 34x3 features
function output3D = tECDF(x,y,z)

% ECDF

IND=0;
j=1; i=1;
while (j<=columns(x))     
     IND(1,i)=j;     j=j+6;     i=i+1;
endwhile

[F,X]=ecdf(x(1,:));
ECDF=X'(1,IND);
for i=2:rows(x)    
    [F,X]=ecdf(x(i,:));
    ECDF = [ECDF ; X'(1,IND)];  
endfor 
output3D = ECDF;

[F,Y]=ecdf(y(1,:));
ECDF=Y'(1,IND);
for i=2:rows(y)    
    [F,Y]=ecdf(y(i,:));
    ECDF = [ECDF ; Y'(1,IND)];  
endfor 
output3D = [output3D ECDF];

[F,Z]=ecdf(z(1,:));
ECDF=Z'(1,IND);
for i=2:rows(z)    
    [F,Z]=ecdf(z(i,:));
    ECDF = [ECDF ; Z'(1,IND)];  
endfor 
output3D = [output3D ECDF];



endfunction


%% FEATURES ORIGINALES 


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% function output3D = tfeatures3D(x,y,z)
%
% 40 features
function output3D = tfeatures3D(x,y,z)
output3D = mean(x,2); output3D = [output3D mean(y,2)]; output3D = [output3D mean(z,2)];
prueba=std(x,0,2); output3D = [output3D prueba];
prueba=std(y,0,2); output3D = [output3D prueba];
prueba=std(z,0,2); output3D = [output3D prueba];
prueba=mad(x,1,2); output3D = [output3D prueba];
prueba=mad(x,1,2); output3D = [output3D prueba];
prueba=mad(z,1,2); output3D = [output3D prueba];

output3D = [output3D max(x,[],2)]; output3D = [output3D max(y,[],2)]; output3D = [output3D max(z,[],2)];
output3D = [output3D min(x,[],2)]; output3D = [output3D min(y,[],2)]; output3D = [output3D min(z,[],2)];
output3D = [output3D sum(abs(x)+abs(y)+abs(z),2)/columns(x)];

output3D = [output3D sum(x.^2,2)/columns(x)]; output3D = [output3D sum(y.^2,2)/columns(y)];output3D = [output3D sum(z.^2,2)/columns(z)];
output3D = [output3D iqr(x,2)]; output3D = [output3D iqr(y,2)]; output3D = [output3D iqr(z,2)];

% Entrop�a
for i=1:rows(x)    
    ET(i,1)=entropy(x(i,:));  
endfor 
output3D = [output3D ET];
for i=1:rows(y)    
    ET(i,1)=entropy(y(i,:));  
endfor 
output3D = [output3D ET];
for i=1:rows(z)    
    ET(i,1)=entropy(z(i,:));  
endfor 
output3D = [output3D ET];

[AR RC PE]=lattice(x,4,'BURG'); output3D = [output3D AR]; 
[AR RC PE]=lattice(y,4,'BURG'); output3D = [output3D AR];
[AR RC PE]=lattice(z,4,'BURG'); output3D = [output3D AR];

% Correlaciones
CORR=corr(x',y');
for i=1:rows(x)
  C(i,1)=CORR(i,i);
endfor 
output3D = [output3D C];
CORR=corr(x',z'); 
for i=1:rows(x)
  C(i,1)=CORR(i,i);      
endfor 
output3D = [output3D C];
CORR=corr(y',z');
for i=1:rows(x)
  C(i,1)=CORR(i,i); 
endfor 
output3D = [output3D C];


endfunction

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output1D = tfeatures1D(x)
%
% 13 features
function output1D = tfeatures1D(x)
output1D = mean(x,2);
output1D = [output1D std(x,0,2)];
output1D = [output1D mad(x,1,2)];
output1D = [output1D max(x,[],2)];
output1D = [output1D min(x,[],2)];
output1D = [output1D sum(abs(x),2)/columns(x)];
output1D = [output1D sum(x.^2,2)/columns(x)];
output1D = [output1D iqr(x,2)];

% Entrop�a
for i=1:rows(x)    
    ET(i,1)=entropy(x(i,:));  
endfor 
output1D = [output1D ET];

[AR RC PE]=lattice(x,4,'BURG'); output1D = [output1D AR]; 

endfunction

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output3D = ffeatures3D(x,y,z)
%
% 79 features
function foutput3D = ffeatures3D(x,y,z)
foutput3D = mean(x,2); foutput3D = [foutput3D mean(y,2)]; foutput3D = [foutput3D mean(z,2)];
foutput3D = [foutput3D std(x,0,2)]; foutput3D = [foutput3D std(y,0,2)]; foutput3D = [foutput3D std(z,0,2)];
foutput3D = [foutput3D mad(x,1,2)]; foutput3D = [foutput3D mad(y,1,2)]; foutput3D = [foutput3D mad(z,1,2)];

[m ind] = max(x,[],2); foutput3D = [foutput3D m ind]; 
[m ind] = max(y,[],2); foutput3D = [foutput3D m ind]; 
[m ind] = max(z,[],2); foutput3D = [foutput3D m ind]; 

foutput3D = [foutput3D min(x,[],2)]; foutput3D = [foutput3D min(y,[],2)]; foutput3D = [foutput3D min(z,[],2)];
foutput3D = [foutput3D sum(abs(x)+abs(y)+abs(z),2)/columns(x)];
foutput3D = [foutput3D sum(x.^2,2)/columns(x)]; foutput3D = [foutput3D sum(y.^2,2)/columns(y)];foutput3D = [foutput3D sum(z.^2,2)/columns(z)];
foutput3D = [foutput3D iqr(x,2)]; foutput3D = [foutput3D iqr(y,2)]; foutput3D = [foutput3D iqr(z,2)];

% Entrop�a
for i=1:rows(x)    
    ET(i,1)=entropy(x(i,:));  
endfor 
foutput3D = [foutput3D ET];
for i=1:rows(y)    
    ET(i,1)=entropy(y(i,:));  
endfor 
foutput3D = [foutput3D ET];
for i=1:rows(z)    
    ET(i,1)=entropy(z(i,:));  
endfor 
foutput3D = [foutput3D ET];

% meanFreq
for j=1:columns(x)     FreQ(1,j)=j;    endfor 
for i=1:rows(x)    
    suma=sum(x(i,:));  
    meanFreqX(i,1)=dot(FreQ,x(i,:)/suma,2);
endfor 
foutput3D = [foutput3D meanFreqX];
for j=1:columns(y)     FreQ(1,j)=j;    endfor 
for i=1:rows(y)    
    suma=sum(y(i,:));  
    meanFreqY(i,1)=dot(FreQ,y(i,:)/suma,2);
endfor 
foutput3D = [foutput3D meanFreqY];
for j=1:columns(z)     FreQ(1,j)=j;    endfor 
for i=1:rows(z)    
    suma=sum(z(i,:));  
    meanFreqZ(i,1)=dot(FreQ,z(i,:)/suma,2);
endfor 
foutput3D = [foutput3D meanFreqZ];

% Kurtosis
foutput3D = [foutput3D kurtosis(x,1,2) kurtosis(y,1,2) kurtosis(z,1,2)];
 
% Skewness
foutput3D = [foutput3D skewness(x,1,2) skewness(y,1,2) skewness(z,1,2)];

% Energ�a por bandas
salto=int32((columns(x)/8)-0.5);
for i=1:8    
  foutput3D = [foutput3D sum(x(:,((i-1)*salto+1):i*salto),2)];    
endfor 
salto=int32((columns(x)/6)-0.5);
for i=1:6    
  foutput3D = [foutput3D sum(x(:,(i-1)*salto+1:i*salto),2)];    
endfor 
salto=int32((columns(x)/8)-0.5);
for i=1:8    
  foutput3D = [foutput3D sum(y(:,(i-1)*salto+1:i*salto),2)];    
endfor 
salto=int32((columns(x)/6)-0.5);
for i=1:6    
  foutput3D = [foutput3D sum(y(:,(i-1)*salto+1:i*salto),2)];    
endfor 
salto=int32((columns(x)/8)-0.5);
for i=1:8    
  foutput3D = [foutput3D sum(z(:,(i-1)*salto+1:i*salto),2)];    
endfor 
salto=int32((columns(x)/6)-0.5);
for i=1:6    
  foutput3D = [foutput3D sum(z(:,(i-1)*salto+1:i*salto),2)];    
endfor 

endfunction


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function foutput1D = ffeatures1D(x,y,z)
%
% 13 features
function foutput1D = ffeatures1D(x)
foutput1D = mean(x,2);
foutput1D = [foutput1D std(x,0,2)];
foutput1D = [foutput1D mad(x,1,2)];

[m ind] = max(x,[],2); foutput1D = [foutput1D m ind]; 

foutput1D = [foutput1D min(x,[],2)];
foutput1D = [foutput1D sum(abs(x),2)/columns(x)];
foutput1D = [foutput1D sum(x.^2,2)/columns(x)];
foutput1D = [foutput1D iqr(x,2)]; 

% Entrop�a
for i=1:rows(x)    
    ET(i,1)=entropy(x(i,:));  
endfor 
foutput1D = [foutput1D ET];

% meanFreq
for j=1:columns(x)     FreQ(1,j)=j;    endfor 
for i=1:rows(x)    
    suma=sum(x(i,:),2);  
    meanFreqX(i,1)=dot(FreQ,x(i,:)/suma,2);
endfor 
foutput1D = [foutput1D meanFreqX];

% Kurtosis
foutput1D = [foutput1D kurtosis(x,1,2)];
 
% Skewness
foutput1D = [foutput1D skewness(x,1,2)];

endfunction


function angles = angle_computation(x,y)
for i=1:rows(x)        
    CosTheta = dot(x(i,:),y(i,:),2)/(norm(x(i,:))*norm(y(i,:)));    ThetaInDegrees = abs(acos(CosTheta))*180/pi;
    angles(i,1)=ThetaInDegrees;
endfor 

endfunction

