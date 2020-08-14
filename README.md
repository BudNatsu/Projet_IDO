# Projet_IDO

Projet IDO 2019-2020
Sujet : Réceptionner les informations émises par les avions et les traiter. (ADS-B)
But : Concevoir une solution permettant la réception et le traitement d'information sur Raspberry pi en utilisant un minimum de logiciels.

  - Logiciels utilisés : Gnuradio-companion, Dump1090, Telegraf, InfluxDB, Grafana, VirtualBox (serveur) 
  - Matériels utilisés : Raspberry pi, NooElec NESDR Mini 2+ 
   - Plugins utilisés : Plugins par défaut, Trackmap, Langages utilisés : Bash, Python
   - Création d'une application Android permettant la connexion vers une base de données InfluxDB et permettant l'affichage d'un avion sur une carte avec la position.

Idées : Rendre les dispositifs mobile un maximum, on pourra donc distribuer les dispositifs aux camionneurs afin qu'ils reçoivent et émettent partout sur le territoire.
Dans certains cas, certains dispositifs deviendront des stations fixes, si les personnes souhaitent les utiliser depuis leurs domiciles.
Si c'est une station mobile alors on peut utiliser un  Base Shield 3G-4G/LTE, sinon si c'est une station fixe alors il faut privilégier le Wi-Fi ou Ethernet
