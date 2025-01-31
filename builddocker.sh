#!/bin/bash
DOCKERIMAGE=aacazxnat/xnatbruker
date=`date +%m/%d/%Y`
IMVER=0.4

sed -i "/__version__=/c\__version__=${IMVER}" ./src/uploadraw.py

echo "${DOCKERIMAGE}" > ./src/version
echo "version ${IMVER}" >> ./src/version
echo "built on $date" >> ./src/version
echo "${DOCKERIMAGE} ${VER}" > ./src/readme
echo -e "Container for XNAT and Bruker integration:\n\t*\txnat==0.4.3\n\t*\tnipype==1.8.3\n\t*\tjupyterlab==3.4.4\n\t*\tnotebook==6.4.12\n\t*\tbruker==0.3.7\n\t*\tdicomifier==2.3.0" >> ./src/readme

if [ $1 = "nocache" ]
then
  echo "build from scratch"
  echo "docker build --no-cache -t ${DOCKERIMAGE}:${IMVER} "
  docker build --no-cache -t ${DOCKERIMAGE}:${IMVER} .
else
  echo "docker build -t ${DOCKERIMAGE}:${IMVER}"
  docker build -t ${DOCKERIMAGE}:${IMVER} .
fi 
docker push ${DOCKERIMAGE}:${IMVER}
