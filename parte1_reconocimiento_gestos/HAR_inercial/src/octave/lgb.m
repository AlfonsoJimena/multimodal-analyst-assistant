function b=vqlbg(v,k) 
% VQLBG Vector quantization using the Linde-Buzo-Gray algorithm 
% 
% Inputs: 
% v contains training data vectors (one per column) 
% k is number of centroids required 
% 
% Outputs: 
% c contains the result VQ codebook (k columns, one for each centroids) 
c=mean(v,2); 
figure(8); 
plot(c(:,:),'.'); 
title('initial codebook'); 
%pause 
e=0.01; 
c(:,1)=c(:,1)+c(:,1)*e; 
figure(9); 
plot(c(:,:),'.'); 
title('codebook1'); 
%pause 
c(:,2)=c(:,1)-c(:,1)*e 
figure(10); 
plot(c(:,:),'.'); 
title('codebook2'); 
%pause 
% Nearest Neighbour Searching. 
% Given a current codebook 'c', assign each training vector in 'v' with the 
% closest codeword. Using the function disteu2, the distances between these 
% vectors (v and c) are computed. 
d=disteu(v,c); [m,id]=min(d,[],2); 
[rows,cols]=size(c); 
% The centroids of the vectors are found using the mean function. 
for j=1:cols 
c(:,j)=mean(v(:,find(id==j)),2); 
end
 figure(11); 
plot(c(:,:),'.'); 
title('new cluster'); 
%pause 
% for each training vector, find the closest codeword using the min 
% function. 
n=1;n=n*2; 
while cols<16 
for i=1:cols 
c(:,i)=c(:,i)+c(:,i)*e; 
c(:,i+n)=c(:,i)-c(:,i)*e; 
d=disteu(v,c); 
[m,i]=min(d,[],2); 
[rows,cols]=size(c); 
end 
figure(12); 
plot(c(:,:),'.'); 
title('updated'); 
%pause 
% The centroids of the vectors are found using the mean function. 
for j=1:cols 
if find(i==j)~isempty(c); 
c(:,j)=mean(v(:,find(i==j)),2); 
end 
end 
n=n*2; 
end


function d = disteu(x, y)
% DISTEU Pairwise Euclidean distances between columns of two matrices
% Input:
%       x, y:   Two matrices whose each column is an a vector data.
% Output:
%       d:      Element d(i,j) will be the Euclidean distance between two
%               column vectors X(:,i) and Y(:,j)
% Note:
%       The Euclidean distance D between two vectors X and Y is:
%       D = sum((x-y).^2).^0.5
[M, N] = size(x);
[M2, P] = size(y); 
if(M ~= M2),
  error('Matrix dimensions do not match.')
end
d = zeros(N, P);
if(N < P),
  copies = zeros(1,P);
  for n = 1:N,
    d(n,:) = sum((x(:, n+copies) - y) .^2, 1);
  end
else
  copies = zeros(1,N);
  for p = 1:P,
    d(:,p) = sum((x - y(:, p+copies)) .^2, 1)';
  end
end
d = d.^0.5;


