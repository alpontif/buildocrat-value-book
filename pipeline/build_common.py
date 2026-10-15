import math, re
SC = {'AB':'Abia','AD':'Adamawa','AK':'Akwa Ibom','AN':'Anambra','BA':'Bauchi','BY':'Bayelsa','BE':'Benue','BR':'Borno','CR':'Cross River','DE':'Delta','EB':'Ebonyi','ED':'Edo','EK':'Ekiti','EN':'Enugu','FC':'FCT, Abuja','GM':'Gombe','IM':'Imo','JI':'Jigawa','KD':'Kaduna','KN':'Kano','KT':'Katsina','KE':'Kebbi','KG':'Kogi','KW':'Kwara','LA':'Lagos','NA':'Nasarawa','NI':'Niger','OG':'Ogun','ON':'Ondo','OS':'Osun','OY':'Oyo','PL':'Plateau','RI':'Rivers','SK':'Sokoto','TA':'Taraba','YB':'Yobe','ZA':'Zamfara'}
SLUG2C = {'abia':'AB','abuja':'FC','adamawa':'AD','akwa-ibom':'AK','anambra':'AN','bauchi':'BA','bayelsa':'BY','benue':'BE','borno':'BR','cross-river':'CR','delta':'DE','ebonyi':'EB','edo':'ED','ekiti':'EK','enugu':'EN','gombe':'GM','imo':'IM','jigawa':'JI','kaduna':'KD','kano':'KN','katsina':'KT','kebbi':'KE','kogi':'KG','kwara':'KW','lagos':'LA','nasarawa':'NA','niger':'NI','ogun':'OG','ondo':'ON','osun':'OS','oyo':'OY','plateau':'PL','rivers':'RI','sokoto':'SK','taraba':'TA','yobe':'YB','zamfara':'ZA'}
CAPITAL = {'AB':'Umuahia','AD':'Yola','AK':'Uyo','AN':'Awka','BA':'Bauchi','BY':'Yenagoa','BE':'Makurdi','BR':'Maiduguri','CR':'Calabar','DE':'Asaba','EB':'Abakaliki','ED':'Benin City','EK':'Ado Ekiti','EN':'Enugu','FC':'Abuja','GM':'Gombe','IM':'Owerri','JI':'Dutse','KD':'Kaduna','KN':'Kano','KT':'Katsina','KE':'Birnin Kebbi','KG':'Lokoja','KW':'Ilorin','LA':'Ikeja','NA':'Lafia','NI':'Minna','OG':'Abeokuta','ON':'Akure','OS':'Osogbo','OY':'Ibadan','PL':'Jos','RI':'Port Harcourt','SK':'Sokoto','TA':'Jalingo','YB':'Damaturu','ZA':'Gusau'}
CAP_LL = {'AB':(5.5249,7.4945),'AD':(9.2035,12.4954),'AK':(5.0377,7.9128),'AN':(6.2104,7.0741),'BA':(10.3103,9.8439),'BY':(4.9267,6.2676),'BE':(7.7322,8.5391),'BR':(11.8333,13.1500),'CR':(4.9757,8.3417),'DE':(6.1980,6.7290),'EB':(6.3249,8.1137),'ED':(6.3350,5.6037),'EK':(7.6211,5.2215),'EN':(6.4584,7.5464),'FC':(9.0579,7.4951),'GM':(10.2897,11.1673),'IM':(5.4850,7.0350),'JI':(11.7562,9.3389),'KD':(10.5105,7.4165),'KN':(12.0022,8.5920),'KT':(12.9908,7.6018),'KE':(12.4539,4.1975),'KG':(7.8023,6.7333),'KW':(8.4966,4.5421),'LA':(6.6018,3.3515),'NA':(8.4939,8.5153),'NI':(9.5836,6.5463),'OG':(7.1475,3.3619),'ON':(7.2571,5.2058),'OS':(7.7827,4.5418),'OY':(7.3775,3.9470),'PL':(9.8965,8.8583),'RI':(4.8156,7.0498),'SK':(13.0059,5.2476),'TA':(8.8833,11.3667),'YB':(11.7470,11.9608),'ZA':(12.1704,6.6641)}
# Nationally dominant metros: Lagos Island core and Abuja core pull values in their commuter belts
METRO = [('Lagos',6.4550,3.4200),('Abuja',9.0579,7.4951),('Port Harcourt',4.8156,7.0498),('Ibadan',7.3775,3.9470),('Kano',12.0022,8.5920)]

def norm(s):
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r"\(.*?\)", ' ', s)
    s = re.sub(r"[^a-z0-9 ]+", ' ', s)
    s = re.sub(r"\b(district|districts|local government|lga|area council|municipal|town|city|estate|layout|phase\s*\d*|state|federal capital territory|fct|axis|main|extension|ext)\b", ' ', s)
    return re.sub(r"\s+", ' ', s).strip()

def hav(la1, lo1, la2, lo2):
    R=6371; t=math.pi/180; h=math.sin((la2-la1)*t/2)**2+math.cos(la1*t)*math.cos(la2*t)*math.sin((lo2-lo1)*t/2)**2
    return 2*R*math.asin(math.sqrt(h))

