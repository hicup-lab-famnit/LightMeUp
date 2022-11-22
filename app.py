## Required libs
import numpy as np
import pandas as pd
from flask import Flask, flash, request, redirect, url_for
from werkzeug.utils import secure_filename
from json import JSONEncoder
import os 


UPLOAD_FOLDER = './img'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app=Flask(__name__,static_folder=os.path.abspath("./build"),static_url_path='/')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#####===============DEFINITIONS AND HELPER FUNCTIONS========########
DEFAULT_PAPER_TYPE="CP80"
T_CP80_p_i_DATA ='./data/inks_spectral_transmittance_data.xlsx'
T_p_DATASET='./data/papers_spectral_trasmittance_data.xlsx'
S_DATASET = './data/observers_spectral_data.xlsx'
E_DATASET ='./data/ipad_spectral_transmittance_data.xlsx'

## Setup for images
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
## Gets data frame from file 
def GetDataFrame(path ,type=None):
   return pd.read_excel(path, type)

### Gets the names of sheets
def GetBookSheetsNames(df):
   return df.keys()

### Makes a dictionary fron GetBookSheet()
def MakeList(data):
   temp=[]
   for d in data:
      temp.append(d)
   return temp

S_OPTIONS = MakeList(GetBookSheetsNames(GetDataFrame(S_DATASET)))
E_OPTIONS = MakeList(GetBookSheetsNames(GetDataFrame(E_DATASET)))
T_CP80_p_i_OPTIONS = MakeList(GetBookSheetsNames(GetDataFrame(T_CP80_p_i_DATA)))

def MakeRGBDictonary(data):
   temp={"red":0, "green":1, "blue":2}
   i=0
   for channel in temp:
      temp[channel]=FitDataToWavelenght(data[i])
      i+=1
   return temp
   
def FitDataToWavelenght(values):
   wl=np.arange(start=400, stop=730, step=10)
   return dict(zip(map(str, wl), values))

def GeneratorRGBVals(channels, whiteRef, kCustom,kB, Multiplier=1):
    #TEMP=[(((channels[0]/whiteRef[0])*const)/255)*kCustom+kB, (((channels[1]/whiteRef[1])*const)/255)*kCustom+kB,(((channels[2]/whiteRef[2])*const)/255)*kCustom+kB]
   TEMP=[((channels[0]/whiteRef[0])*Multiplier*kCustom)+kB,((channels[1]/whiteRef[1])*Multiplier*kCustom)+kB,((channels[2]/whiteRef[2])*Multiplier*kCustom)+kB]
   return np.rint(TEMP).tolist()
    

def IntegrationRGB (s,layer,e, isInkType=True):
   # Spectral data from ipad v1 is a measurement captrure by me and v2 is the one captured with kuba
   # the file contains white, red, green and blue data in each row
   E=GetDataFrame(E_DATASET,e)
   
   W=E.to_numpy()[0]
   R=E.to_numpy()[1]
   G=E.to_numpy()[2]
   B=E.to_numpy()[3]
   
   E_w=W*layer
   E_r=R*layer
   E_g=G*layer
   E_b=B*layer
   
   if(isInkType):
      return ComputeRGBVals (E_r,E_g,E_b,s)
   else:
     
      BGc=ComputeIntegration(E_w,s)
      TEMPc=ComputeRGBVals (E_r,E_g,E_b,s)
      TEMPc.insert(0, BGc)
      
      BG=ComputeIntegration(W,s)
      TEMPn=ComputeRGBVals (R,G,B,s)
      TEMPn.insert(0, BG)
      return [TEMPc,TEMPn]
      
  
def ComputeRGBVals (e_r,e_g,e_b,s):
    R=ComputeIntegration(e_r,s)
    G=ComputeIntegration(e_g,s)
    B=ComputeIntegration(e_b,s)
    return [R,G,B]      
      
##(array,2D array)
def ComputeIntegration(channel,s):
   dx=0.01
   t_r=channel*s[0]
   t_g=channel*s[1]
   t_b=channel*s[2]
   R=np.trapz(t_r,dx=dx)
   G=np.trapz(t_g,dx=dx)
   B=np.trapz(t_b,dx=dx)
   return [R,G,B]


## Color(array or constant), Channels (RGB array), Multiplier (potional number 1-255)
## This funciton is for Normal method (lambda by lambda)
def GenericMultiplication(color,channels,kCustom, kB,multiplier=1):
    TEMP=[]
    for channel in channels:
        TEMP.append(np.rint((channel*color*multiplier*kCustom)+kB))
    return TEMP

#####===============API========########

## RENDERS  UI 
@app.route('/',methods=['GET'])
def index():   
   return app.send_static_file('index.html')

## Handles images
@app.route('/uploadFile',methods=['GET', 'POST'])
def uploaded_file():
   if request.method == 'POST':
         # check if the post request has the file part
         if 'file' not in request.files:
               flash('No file part')
               return redirect(request.url)
         file = request.files['file']
         # if user does not select file, browser also
         # submit an empty part without filename
         if file.filename == '':
               flash('No selected file')
               return redirect(request.url)
         if file and allowed_file(file.filename):
               filename = secure_filename(file.filename)
               file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
               return redirect(url_for('uploaded_file',
                                       filename=filename))
   return redirect(request.url)


## Main interaction with API
@app.route('/updateData',methods = ['POST', 'GET'])
def DataManager():
    ## if request is done, we return the names of the available data in .xlsx files 
    ## and data accordingly to user's configuration (see GetData()). 
    ## This version allow user to control custom brighness (KW_PARAM,KB_PARAM)
    ## DEFAULT_PAPER_TYPE is CP80 as the collected data of inks was done using this specific paper for this research.
    if request.method == 'POST':
      return {
         'digObs': S_OPTIONS,
         'inks': T_CP80_p_i_OPTIONS, 
         'emmiters': E_OPTIONS,
         'defaultData':GetData(request.json["observer"],
                                 DEFAULT_PAPER_TYPE,
                                 request.json["emitter"],
                                 request.json["kW"], 
                                 request.json["kB"])
         }
      
def GetData(s,paperType,e,kW,kB):
      ##Read files
      S=GetDataFrame(S_DATASET,s)
      paper=GetDataFrame(T_p_DATASET,paperType)  
      ##Compute data (df s,df paper, df e, int kW, int kB, string inktype(default inkjet),bool isInkType (default true))
      inkjet=ComputeData(S,paper,e,kW,kB)
      laser=ComputeData(S,paper,e,kW,kB,"laser")
      bg=ComputeData(S,paper,e,kW,kB,isInkType=False)
      
      ##Return json object
      return  {"inkjet":inkjet, "laser":laser, "bg":bg}
   
      
##Compute data (df s,df paper, df e, int kW, int kB, string inktype(default inkjet),bool isInkType (default true))
def ComputeData(s,paper,e,kW,kB,ink="inkjet",isInkType=True):
   ## CUSTOM BRIGHTNESS 05.02.2022 (We limit the amount of whitness using low(kB) and high(kW) limits)
   ## Pixel Value = (Lambda*(kW-kB))+kB
   kCustom=(kW-kB)
   
   ###Data follows the definitions from Blackboad(p.39, 2.4.2021)
   wl=np.arange(start=400, stop=730, step=10)
   
   ##Default Paper plus ink (CP80)
   T_CP80_p_i=GetDataFrame(T_CP80_p_i_DATA,ink)
   
   #Observer data per channel (S) - NORMALIZED
   R=s.to_numpy()[0]
   G=s.to_numpy()[1]
   B=s.to_numpy()[2] 
   
   #JUST PAPER -NORMALIZED after division (transmittance is 0-100)
   T_p=paper.to_numpy()[0]/100
   
   #Ink + paper -NORMALIZED after division (transmittance is 0-100)
   T_p_c=T_CP80_p_i.to_numpy()[0]/100
   T_p_m=T_CP80_p_i.to_numpy()[1]/100
   T_p_y=T_CP80_p_i.to_numpy()[2]/100
         
   #Ink CWR(1/ (ink+paper/paper)) 
   C_cwr=1/(T_p_c/T_p)
   M_cwr=1/(T_p_m/T_p)
   Y_cwr=1/(T_p_y/T_p)
   
   ######LAMBDA BY LAMBDA (NORMAL APPROACH)######
   ## Black board 2.4.2021
   ##NORMAL APPROACH (CHECKED)##
   ##NON-CORRECTED VALUES##
   bgColors=GenericMultiplication(1,[R,G,B], kCustom, kB,0.255)
   cyanColors=GenericMultiplication(C_cwr,[R,G,B], kCustom, kB,0.00255)
   magentaColors=GenericMultiplication(M_cwr,[R,G,B],kCustom, kB,0.00255)
   yellowColors=GenericMultiplication(Y_cwr,[R,G,B],kCustom, kB,0.00255)
   
   ##NORMAL APPROACH (CHECKED)##  
   ##CORRECTED VALUES## (This apporach includes trnamittance of paper plus ink)
   bgColors_corrected=GenericMultiplication(T_p,[R,G,B],kCustom, kB)
   cyanColors_corrected=GenericMultiplication(T_p_c,[R,G,B],kCustom, kB)
   magentaColors_corrected=GenericMultiplication(T_p_m,[R,G,B],kCustom, kB)
   yellowColors_corrected=GenericMultiplication(T_p_y,[R,G,B],kCustom, kB)
   
   ###### INTEGRATION APPROACH (CHECKED)#####
   ##CORRECTED VALUES##   
   ## BGi contains corrected and non corrected values
   BGi=IntegrationRGB([R,G,B],T_p,e,False)
  
   ##NON-CORRECTED VALUES##
   BGNCO= BGi[1]
   BR= BGNCO[0][0]
   BG= BGNCO[0][1]
   BB= BGNCO[0][2]
   
    ##BG integration corrected values
   BGCO= BGi[0]
   BRc= BGCO[0][0]
   BGc= BGCO[0][1]
   BBc=  BGCO[0][2]
#INKSi=IntegrationRGB([R,G,B],[Cc,Mm,Yy],True)
  

   if(isInkType):
      ##  COMPUTE FOREGROUNDS

       ##HARCODED VALUES
       ##per layer-> returns an array [l_bg->r,l_bg->g,l_bg->b]: where l is the layer parsed
       ### each value in array is an array with 3 values [r g b]. 
       ###This are the rbg values per layer used in differetn backgorunds
       C_rgb=IntegrationRGB([R,G,B],T_p_c,e)
       M_rgb=IntegrationRGB([R,G,B],T_p_m,e)
       Y_rgb=IntegrationRGB([R,G,B],T_p_y,e)
       
       Ccwr_rgb=IntegrationRGB([R,G,B],C_cwr,e)
       Mcwr_rgb=IntegrationRGB([R,G,B],M_cwr,e)
       Ycwr_rgb=IntegrationRGB([R,G,B],Y_cwr,e)
       
       ###Correction
       ##CORRECTED
       BG_corrected=[BRc,BGc,BBc]
       REDCYAN_c=GeneratorRGBVals(C_rgb[0],BG_corrected, kCustom, kB)
       REDMAGE_c=GeneratorRGBVals(M_rgb[0],BG_corrected,kCustom, kB)
       REDYELL_c=GeneratorRGBVals(Y_rgb[0],BG_corrected,kCustom, kB)

       GREENCYAN_c=GeneratorRGBVals(C_rgb[1],BG_corrected,kCustom, kB)
       GREENMAGE_c=GeneratorRGBVals(M_rgb[1],BG_corrected,kCustom, kB)
       GREENYELL_c=GeneratorRGBVals(Y_rgb[1],BG_corrected,kCustom, kB)
       
       BLUECYAN_c=GeneratorRGBVals(C_rgb[2],BG_corrected,kCustom, kB)
       BLUEMAGE_c=GeneratorRGBVals(M_rgb[2],BG_corrected,kCustom, kB)
       BLUEYELL_c=GeneratorRGBVals(Y_rgb[2],BG_corrected,kCustom, kB)
       ###NON CORRECTED
       BG_non_corrected=[BR,BG,BB]

       REDCYAN=GeneratorRGBVals(Ccwr_rgb[0],BG_non_corrected, kCustom, kB,0.0255)
       REDMAGE=GeneratorRGBVals(Mcwr_rgb[0],BG_non_corrected, kCustom, kB,0.0255)
       REDYELL=GeneratorRGBVals(Ycwr_rgb[0],BG_non_corrected,kCustom, kB,0.0255)
      
       GREENCYAN=GeneratorRGBVals(Ccwr_rgb[1],BG_non_corrected, kCustom, kB,0.0255)
       GREENMAGE=GeneratorRGBVals(Mcwr_rgb[1],BG_non_corrected, kCustom, kB,0.0255)
       GREENYELL=GeneratorRGBVals(Ycwr_rgb[1],BG_non_corrected, kCustom, kB,0.0255)
      
       BLUECYAN=GeneratorRGBVals(Ccwr_rgb[2],BG_non_corrected, kCustom, kB,0.0255)
       BLUEMAGE=GeneratorRGBVals(Mcwr_rgb[2],BG_non_corrected, kCustom, kB,0.0255)
       BLUEYELL=GeneratorRGBVals(Ycwr_rgb[2],BG_non_corrected, kCustom, kB,0.0255)
       ###Json wrappers
       cColors_=MakeRGBDictonary(cyanColors)
       mColors_=MakeRGBDictonary(magentaColors)
       yColors_=MakeRGBDictonary(yellowColors)
       cColors_c_=MakeRGBDictonary(cyanColors_corrected)
       mColors_c_=MakeRGBDictonary(magentaColors_corrected)
       yColors_c_=MakeRGBDictonary(yellowColors_corrected) 
       data={
         "cColors":cColors_,
         "mColors":mColors_,
         "yColors":yColors_,
         "cColors_c":cColors_c_,
         "mColors_c":mColors_c_,
         "yColors_c":yColors_c_,
         
         "rInks_c_cyan":REDCYAN_c,
         "rInks_c_magenta":REDMAGE_c,
         "rInks_c_yellow":REDYELL_c,
         "gInks_c_cyan":GREENCYAN_c,
         "gInks_c_magenta":GREENMAGE_c,
         "gInks_c_yellow":GREENYELL_c,
         "bInks_c_cyan":BLUECYAN_c,
         "bInks_c_magenta":BLUEMAGE_c,
         "bInks_c_yellow":BLUEYELL_c,

         "rInks_cyan":REDCYAN,
         "rInks_magenta":REDMAGE,
         "rInks_yellow":REDYELL,
         "gInks_cyan":GREENCYAN,
         "gInks_magenta":GREENMAGE,
         "gInks_yellow":GREENYELL,
         "bInks_cyan":BLUECYAN,
         "bInks_magenta":BLUEMAGE,
         "bInks_yellow":BLUEYELL,
            }
       
       return data

   else:
      ##  COMPUTE BACKGROUNDS
      RBGc=GeneratorRGBVals(BGCO[1],[BRc,BGc,BBc], kCustom, kB)
      GBGc=GeneratorRGBVals(BGCO[2],[BRc,BGc,BBc], kCustom, kB)
      BBGc=GeneratorRGBVals(BGCO[3],[BRc,BGc,BBc],kCustom, kB)
      
      RBG=GeneratorRGBVals(BGNCO[1],[BR,BG,BB], kCustom, kB)
      GBG=GeneratorRGBVals(BGNCO[2],[BR,BG,BB], kCustom, kB)
      BBG=GeneratorRGBVals(BGNCO[3],[BR,BG,BB], kCustom, kB)
      bgColors_corrected_dic= MakeRGBDictonary(bgColors_corrected)
      bgColors_dic=MakeRGBDictonary(bgColors)
      
      data={
         "bgColors_c": bgColors_corrected_dic, 
         "bgColors": bgColors_dic,
         "rMono_c": RBGc,
         "gMono_c": GBGc,
         "bMono_c": BBGc,
         "rMono":RBG,
         "gMono":GBG,
         "bMono":BBG,
      }
      return data

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True)
