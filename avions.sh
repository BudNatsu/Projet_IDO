#!/bin/bash

cd /home/buddy/projet_ido/git2/dump1090
sudo ./dump1090 --interactive --net --net-sbs-port 30003 --write-json public_html/data
#cd public_html 
#python -m SimpleHTTPServer 8090 &
