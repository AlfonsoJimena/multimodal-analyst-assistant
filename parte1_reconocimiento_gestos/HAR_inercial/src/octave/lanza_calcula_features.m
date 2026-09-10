printf('Calling Octave RASTAPLP ...\n');
pkg load tsa
pkg load image
pkg load statistics
pkg load geometry
pkg load linear-algebra
pkg load signal

calcula_features('lista_fich_s_A_P.lis');
%calcula_features('lista_fich_a_P.lis');
%calcula_features('lista_fich_s_W.lis');
%calcula_features('lista_fich_a_W.lis');

printf('END\n');
