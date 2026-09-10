% MAIN FUNCTION
function calcula_features(list_file)

% Read de list
% list_file='lista_test.lis';
[LIST] = textread (list_file,'%s');
list_file
num_rows = rows(LIST);
for i = 1:num_rows
  processing(char(LIST(i,1)));  
  %printf('%s\n',char(LIST(i,1)))

  endfor
endfunction


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function processing(ini_file)
%
function processing(ini_file)

%ini_file = "SP48_g_samsungold_samsungold_1.ori";

[AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread (ini_file,"%f %f %f %s %s %s %s");

%dev=device(1);
%if (strcmp(dev(1:1),"gear_1")==1)   
%    meanx=3.448134;meany=-3.292766;meanz=1.801478;stdevx=7.863841;stdevy=3.025247;stdevz=3.738042;
%elseif (strcmp(dev(1:1),"gear_2")==1)   
%    meanx=-2.084717;meany=-0.546981;meanz=1.259073;stdevx=7.393649;stdevy=5.812254;stdevz=4.087730;
%elseif (strcmp(dev(1:1),"lgwatch_1")==1)   meanx=-0.377161;meany=-3.077434;meanz=2.270496;stdevx=8.148801;stdevy=4.536140;stdevz=2.942517;
%elseif (strcmp(dev(1:1),"lgwatch_2")==1)   meanx=-3.694463;meany=0.703967;meanz=0.451448;stdevx=6.838718;stdevy=5.479337;stdevz=4.333624;
%elseif (strcmp(dev(1:1),"s3_1")==1)   meanx=-2.294957;meany=0.322408;meanz=8.765656;stdevx=3.651762;stdevy=1.562844;stdevz=2.290384;
%elseif (strcmp(dev(1:1),"s3_2")==1)   meanx=-2.033752;meany=0.332171;meanz=8.550187;stdevx=3.673229;stdevy=1.576381;stdevz=2.253170;
%elseif (strcmp(dev(1:1),"s3mini_1")==1)   meanx=-0.573454;meany=0.383944;meanz=8.487883;stdevx=4.295023;stdevy=1.527287;stdevz=2.105104;
%elseif (strcmp(dev(1:1),"s3mini_2")==1)   meanx=-3.453989;meany=0.618804;meanz=8.263874;stdevx=3.143683;stdevy=1.612498;stdevz=2.319204;
%elseif (strcmp(dev(1:1),"samsungold_1")==1)   meanx=-2.071012;meany=-0.248736;meanz=8.946852;stdevx=3.588360;stdevy=1.569884;stdevz=2.275309;
%elseif (strcmp(dev(1:1),"samsungold_2")==1)   meanx=-0.510094;meany=0.370343;meanz=9.050280;stdevx=4.272776;stdevy=1.504447;stdevz=2.217820;
%elseif (strcmp(dev(1:1),"nexus4_1")==1)   meanx=-1.788415;meany=0.168024;meanz=9.364738;stdevx=3.776353;stdevy=1.487605;stdevz=2.303812;
%elseif (strcmp(dev(1:1),"nexus4_2")==1)   meanx=-1.929721;meany=-0.056396;meanz=8.946360;stdevx=3.664981;stdevy=1.543833;stdevz=2.249974;
%endif
%AccX=(AccX-meanx)/stdevx;
%AccY=(AccY-meany)/stdevy;
%AccZ=(AccZ-meanz)/stdevz;



% PREPROCESO

% Remove mean and variance
%AccX2 =  (AccX-mean(AccX))./(std(AccX)); AccX = AccX2;
%AccY2 =  (AccY-mean(AccY))./(std(AccY)); AccY = AccY2;
%AccZ2 =  (AccZ-mean(AccZ))./(std(AccZ)); AccZ = AccZ2;

% Rotation
%count=0;
%MAccX=MAccY=MAccZ=0;
%for i=0:rows(AccXorig)-1
    
%    if (strcmp(activity(i+1),"stand")==1) 
%       MAccX+=AccXorig(i+1);
%       MAccY+=AccYorig(i+1);
%       MAccZ+=AccZorig(i+1);       
%       count++;
%       if (count>=100) break;  endif
    
%    endif    
 %endfor 

%MAccX/=count;
%MAccY/=count;
%MAccZ/=count;
%MAccX=mean(AccXorig);
%MAccY=mean(AccYorig);
%MAccZ=mean(AccZorig);

%Teta=vectorAngle3d([MAccX MAccY MAccZ],[1 0 0]);
%Axis=cross([MAccX MAccY MAccZ],[1 0 0]);
%AxisNorm=normalizeVector(Axis);
%R=rotv(AxisNorm,Teta);
%ALL=[AccXorig AccYorig AccZorig];
%Out=R*ALL';
%AccX=Out'(:,1);
%AccY=Out'(:,2);
%AccZ=Out'(:,3);

% Nothing
AccX=AccXorig;
AccY=AccYorig;
AccZ=AccZorig;


win_size =150; % 2 segundos a 50 Hz
overlap=100; % 2 segundos a 50 Hz
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

OUTPUT = tfeatures3D(tBodyAccX,tBodyAccY,tBodyAccZ);  % 40 features
OUTPUT = [OUTPUT tfeatures3D(tBodyAccJerkX,tBodyAccJerkY,tBodyAccJerkZ)]; %40 features

OUTPUT = [OUTPUT tfeatures1D(tBodyAccMag)]; %13 features
OUTPUT = [OUTPUT tfeatures1D(tBodyAccJerkMag)]; %13 features

OUTPUT = [OUTPUT ffeatures3D(fBodyAccX,fBodyAccY,fBodyAccZ)]; %79 features
OUTPUT = [OUTPUT ffeatures3D(fBodyAccJerkX,fBodyAccJerkY,fBodyAccJerkZ)]; %79 features

OUTPUT = [OUTPUT ffeatures1D(fBodyAccMag)]; %13 features
OUTPUT = [OUTPUT ffeatures1D(fBodyAccJerkMag)]; %13 features


% OUTPUT = tECDF(tBodyAccX,tBodyAccY,tBodyAccZ);  % 34+34+34 features
% OUTPUT = frastaplp3D(AccX',AccY',AccZ');  %60 features
% OUTPUT = [OUTPUT fmfcc3D(AccX',AccY',AccZ')];  %60 features



%% HISTOGRAM EQUALIZATION
%%for j=1:columns(OUTPUT) 
%%   COL = OUTPUT(:,j);
%%   COL2= (COL.-min(COL)) ./ (max(COL)-min(COL));
%%   OUTPUT(:,j) = histeq(COL2);
%%endfor 

%% PCA

% eigenvectors
%%mu = mean(OUTPUT);
%%Xm = bsxfun(@minus, OUTPUT, mu);
%%C = cov(Xm);
%%[V,D] = eig(C);
%%num_c=columns(OUTPUT);
% sort eigenvectors desc
%%[D, i] = sort(diag(D), 'descend');
%%V = V(:,i);
% project on pc1
%%OUTPUT = Xm*V(:,1:num_c);
%%z = Xm*V(:,1:num_c);
% and reconstruct it
%%p = z*V(:,1:num_c)';
%%OUTPUT = bsxfun(@plus, p, mu);

%% ICA
%%[Zica A T mu] = myICA(OUTPUT',100);
%%OUTPUT=Zica';
%%Zout = A * OUTPUT';
%%OUTPUT=Zout';
% and reconstruct it
%%Zr = T \ pinv(A) * Zica + repmat(mu,1,rows(OUTPUT));

%% SVD
%%[U, S, V] = svd (OUTPUT);
%% num_c=columns(OUTPUT);
%% A=V(:,1:num_c)';
%% OUTPUT2=OUTPUT*V';


%% Z_SCORE
%OUTPUT2 =  OUTPUT-mean(OUTPUT);
%OUTPUT2 =  (OUTPUT-mean(OUTPUT))./(std(OUTPUT));
%OUTPUT = OUTPUT2;

%OUTPUT3 = deltas(OUTPUT',9);
%OUTPUT = [OUTPUT OUTPUT3'];

for j=1:columns(OUTPUT) 
  for i=1:rows(OUTPUT)      
    if (isnan(OUTPUT(i,j)))   OUTPUT(i,j)=0;    endif
    if (isinf(OUTPUT(i,j)))   OUTPUT(i,j)=0;    endif
  endfor 
endfor 


% IMPRESIÓN FINAL 
user_mode=user(1:rows(OUTPUT));      
model_mode=model(1:rows(OUTPUT));      
device_mode=device(1:rows(OUTPUT));      
activity_mode=activity(1:rows(OUTPUT));
for i=0:rows(OUTPUT)-1           
    user_mode(i+1)=user((i+1)*step);
    model_mode(i+1)=model((i+1)*step);
    device_mode(i+1)=device((i+1)*step);
    activity_mode(i+1)=activity((i+1)*step);
endfor 


[data_file ext]=strtok(ini_file,".");
data_file2=strcat(data_file,'.arff');  
%csvwrite(data_file,user_mode);
fid = fopen (data_file2, "w");

fid2 = fopen ("cabecera.arff", "w");
% Nombres
fprintf(fid2,"@relation %s\n\n",data_file);
    for j=1:columns(OUTPUT)            
       fprintf(fid2,"@attribute %d numeric\n",j);        
    endfor 
%    fprintf(fid2,"user,model,device,activity\n");
    fprintf(fid2,"@attribute activity {stand,sit,walk,stairsdown,stairsup,bike}\n\n@data\n");
fclose (fid2);

for i=0:rows(OUTPUT)-1        
    % OJO
   % if (strcmp(activity_mode(i+1),"null")==1) continue;endif
    
    %fprintf(fid,"0 %d ",i);    
    % OJO
    for j=1:columns(OUTPUT)            
       fprintf(fid,"%f,",OUTPUT(i+1,j));        
    endfor 
    %fprintf(fid,"%s,",char(user_mode(i+1)));fprintf(fid,"%s,",char(model_mode(i+1)));fprintf(fid,"%s,",char(device_mode(i+1)));fprintf(fid,"%s\n",char(activity_mode(i+1)));
    
    %OJO
    fprintf(fid,"%s\n",char(activity_mode(i+1)));
    %fprintf(fid,"%f\n",OUTPUT(i+1,columns(OUTPUT)));        
 endfor 
fclose (fid);

endfunction




%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output3D = frastaplp3D(x,y,z)
%
% 20x3 features
function foutputRASTAPLP3D = frastaplp3D(x,y,z)

sr=8000;
rasta=1;

datax=x';
[mm, spec] = rastaplp(datax, sr, rasta, 19);
foutputRASTAPLP3D = mm';

datay=y';
[mm, spec] = rastaplp(datay, sr, rasta, 19);
foutputRASTAPLP3D = [foutputRASTAPLP3D mm'];

dataz=z';
[mm, spec] = rastaplp(dataz, sr, rasta, 19);
foutputRASTAPLP3D = [foutputRASTAPLP3D mm'];


endfunction



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
% function output3D = fmfcc3D(x,y,z)
%
% 20x3 features
function foutputMFCC3D = fmfcc3D(x,y,z)

sr=8000;
num_cep=20;
num_bands=40;

datax= x';
[mm,aspc] = melfcc(datax, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
foutputMFCC3D = mm';

datay= y';
[mm,aspc] = melfcc(datay, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
foutputMFCC3D = [foutputMFCC3D mm'];

dataz= z';
[mm,aspc] = melfcc(dataz, sr, 'maxfreq', 4000, 'numcep', num_cep, 'nbands', num_bands, 'fbtype', 'fcmel', 'dcttype', 3, 'usecmp', 1, 'wintime', 0.01875, 'hoptime', 0.00625, 'preemph', 0, 'dither', 0);
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
prueba=mad(y,1,2); output3D = [output3D prueba];
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
%CORR=corr(x',y');
%for i=1:rows(x)    C(i,1)=CORR(i,i);      endfor 
for i=1:rows(x)    C(i,1)=corr(x(i,:)',y(i,:)');      endfor 

output3D = [output3D C];
%CORR=corr(x',z'); 
%for i=1:rows(x)    C(i,1)=CORR(i,i);      endfor 
for i=1:rows(x)    C(i,1)=corr(x(i,:)',z(i,:)');      endfor 
output3D = [output3D C];
%CORR=corr(y',z');
%for i=1:rows(x)    C(i,1)=CORR(i,i);      endfor 
for i=1:rows(x)    C(i,1)=corr(y(i,:)',z(i,:)');      endfor 
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

