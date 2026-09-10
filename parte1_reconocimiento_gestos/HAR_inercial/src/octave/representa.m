pkg load tsa
pkg load image
pkg load statistics
pkg load geometry
pkg load linear-algebra
pkg load signal
graphics_toolkit('gnuplot')

 figure(1)
 %[AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread ("SeAW_a_gear_gear_1.ori","%f %f %f %s %s %s %s");
 [AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread ("SeAP_i_nexus4_nexus4_1.ori","%f %f %f %s %s %s %s");
 
Acc=medfilt1([AccXorig AccYorig AccZorig],500);

AccXorig=Acc(:,1);
AccYorig=Acc(:,2);
AccZorig=Acc(:,3);
  figure(1)

 s1=ones(rows(AccXorig),1);
 s1=s1.*4;
 
 LABELS=activity;
 L=zeros(rows(LABELS),1);

if (strcmp(char(LABELS(1)),"sit")==1)  L(1)= 1; 
elseif (strcmp(char(LABELS(1)),"stand")==1)  L(1)=2; 
elseif (strcmp(char(LABELS(1)),"bike")==1)  L(1)=3; 
elseif (strcmp(char(LABELS(1)),"walk")==1)  L(1)=5; 
elseif (strcmp(char(LABELS(1)),"stairsdown")==1)  L(1)=4; 
elseif (strcmp(char(LABELS(1)),"stairsup")==1)  L(1)=6; 
elseif (strcmp(char(LABELS(1)),"null")==1)  L(1)=0; 
endif

for n=2:rows(LABELS)      
    if (strcmp(char(LABELS(n)),"sit")==1)  L(n)= 1; 
   elseif (strcmp(char(LABELS(n)),"stand")==1)  L(n)=2; 
   elseif (strcmp(char(LABELS(n)),"bike")==1)  L(n)=3; 
   elseif (strcmp(char(LABELS(n)),"walk")==1)  L(n)=5; 
   elseif (strcmp(char(LABELS(n)),"stairsdown")==1)  L(n)=4; 
   elseif (strcmp(char(LABELS(n)),"stairsup")==1)  L(n)=6; 
   elseif (strcmp(char(LABELS(n)),"null")==1)  L(n)=0; 
   endif
endfor 
 size(L)
   
 scatter3(AccXorig,AccYorig,AccZorig,s1,L);
%axis([-20 20 -20 20 -20 20])
axis([-10 10 -10 10 -10 10])
 %plot3(AccXorig,AccYorig,AccZorig);
 
  figure(2)
 [AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread ("SeAW_i_lgwatch_lgwatch_1.ori","%f %f %f %s %s %s %s");
 %[AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread ("SeAP_c_s3mini_s3mini_2.ori","%f %f %f %s %s %s %s");
 %[AccXorig,AccYorig,AccZorig,user,model,device,activity] = textread ("SeAW_a_gear_gear_1.ori","%f %f %f %s %s %s %s");
   figure(2)

 s1=ones(rows(AccXorig),1);
 s1=s1.*4;
 
 Acc=medfilt1([AccXorig AccYorig AccZorig],500);

AccXorig=Acc(:,1);
AccYorig=Acc(:,2);
AccZorig=Acc(:,3);

 
 LABELS=activity;
 L=zeros(rows(LABELS),1);

if (strcmp(char(LABELS(1)),"sit")==1)  L(1)= 1; 
elseif (strcmp(char(LABELS(1)),"stand")==1)  L(1)=2; 
elseif (strcmp(char(LABELS(1)),"bike")==1)  L(1)=3; 
elseif (strcmp(char(LABELS(1)),"walk")==1)  L(1)=5; 
elseif (strcmp(char(LABELS(1)),"stairsdown")==1)  L(1)=4; 
elseif (strcmp(char(LABELS(1)),"stairsup")==1)  L(1)=6; 
elseif (strcmp(char(LABELS(1)),"null")==1)  L(1)=0; 
endif

for n=2:rows(LABELS)      
    if (strcmp(char(LABELS(n)),"sit")==1)  L(n)= 1; 
   elseif (strcmp(char(LABELS(n)),"stand")==1)  L(n)=2; 
   elseif (strcmp(char(LABELS(n)),"bike")==1)  L(n)=3; 
   elseif (strcmp(char(LABELS(n)),"walk")==1)  L(n)=5; 
   elseif (strcmp(char(LABELS(n)),"stairsdown")==1)  L(n)=4; 
   elseif (strcmp(char(LABELS(n)),"stairsup")==1)  L(n)=6; 
   elseif (strcmp(char(LABELS(n)),"null")==1)  L(n)=0; 
   endif
endfor 
 size(L)
   
 scatter3(AccXorig,AccYorig,AccZorig,s1,L);
axis([-10 10 -10 10 -10 10])

 %plot3(AccXorig,AccYorig,AccZorig);
 
 
 