from pathlib import Path
import os, sys, json, re, ast
from decimal import Decimal
from datetime import datetime as DATETIME
import pytz
import CifFile
from CifFile import ReadCif

from Utils.createMaiMLFile import ReadWriteMaiML, UpdateMaiML
from Utils.staticClass import maimlelement, settings


################################################
## FILE DIR PATH 
################################################
class filepath:
    cur_file = __file__  #このファイルのパス
    codedir = os.path.dirname(cur_file) + '/'
    rootdir = os.path.abspath(os.path.join(codedir, os.pardir)) + '/'
    input_dir = codedir + 'INPUT/'
    output_dir = codedir + 'OUTPUT/'
    tmp_dir = codedir + 'TMP/'

################################################
### event要素に設定する日付のフォーマット　
##### YYYY-MM-DDTHH:MM:SS-xx:xx #########
################################################
def formatter_datetime(year,month,day,hour,min,sec,gmtime):
    #print(e_datetime) #2000/3/1 1:00
    vms_datetime = DATETIME(year, month, day, hour, min, sec)
    #print(vms_datetime) # 2000-03-01 01:00:00

    TIME_ZONE = settings.TIME_ZONE #'Asia/Tokyo'
    tokyo_tz = pytz.timezone(TIME_ZONE)
    vms_datetime = tokyo_tz.localize(vms_datetime)
    # 日時を 'YYYY-MM-DDTHH:MM:SS' フォーマットに変換
    datetime_str = vms_datetime.strftime('%Y-%m-%dT%H:%M:%S')

    # タイムゾーンオフセットを取得し、フォーマットを整える（+09:00の形式に）
    offset = vms_datetime.strftime('%z')  # 例: +0900
    formatted_offset = offset[:3] + ':' + offset[3:]  # 例: +09:00

    # 日時とタイムゾーンオフセットを合体
    datetime = f'{datetime_str}{formatted_offset}'
    return datetime


################################################
### CIFデータ値の数値型のフォーマット　
##### 00.0000(nn) --> 00.0000 , 0.00nn #########
################################################
def formatter_standarddeviation(str_value, sd_number):
    def count_decimal_places(str_number):
        # Decimalオブジェクトに変換して処理する
        number = Decimal(str_number)  # 文字列をDecimalにする
        if number % 1 == 0:  # 整数部分が0なら少数部分なし
            return 0
        # 少数部分の桁数を計算
        return len(str(number).split('.')[1])

    def adjust_decimal_places(number, target_digits):
        # 数字を小数部に合わせて調整する
        if target_digits == 0:
            return number  # 少数部が0桁ならそのまま
        else:
            # 数字を小数部の桁数に合わせる
            factor = 10 ** target_digits
            # まずスケーリングしてから、丸めて、再スケーリング
            return round(float(number) / factor, target_digits)

    # test_number の少数部分の桁数を取得
    decimal_places = count_decimal_places(str_value) # valueはstring型
    print('decimal_places:',decimal_places)
    fstring = f"{0:.{decimal_places}f}"
    # test_number2 を test_number の少数部分の桁数に合わせて調整
    adjusted_value = adjust_decimal_places(sd_number, decimal_places)
    print(str_value,'  ', sd_number)
    print('adjusted_value:',adjusted_value)
    
    return fstring, adjusted_value


################################################
### ReadCifで読み込んだCIFデータ値のリスト型のフォーマット　
##### ['xxx', 'yyyy'] --> xxx yyyy #########
################################################
def convert_list(a):
    # 文字列がリストの形式かどうか確認
    try:
        # ast.literal_evalで安全に文字列をリストとして評価
        list_a = ast.literal_eval(a)
        if isinstance(list_a, list):
            # リストが正しく評価されれば、カンマをスペースに変換して返す
            return ' '.join(list_a)
        else:
            return False
    except (ValueError, SyntaxError):
        # リスト形式でない場合はエラーが発生するのでその場合はFalse
        return False


################################################
## results１つが持つ汎用データコンテナと、CIFデータを比較
## keyが一致した場合、汎用データコンテナのvalueにCIFデータを挿入
################################################
def writeValue(generallist1, ciflist):
    new_generallist = []
    for glindex, generaldict in enumerate(generallist1):
        ## propertyListTypeを処理
        new_generaldict = generaldict
        
        # 汎用データコンテナを持つか
        if maimlelement.property in new_generaldict:
            generallist2 = new_generaldict[maimlelement.property] if isinstance(new_generaldict[maimlelement.property],list) else [new_generaldict[maimlelement.property]]
            new_generaldict[maimlelement.property] = writeValue(generallist2,ciflist)
        if maimlelement.content in new_generaldict:
            generallist2 = new_generaldict[maimlelement.content] if isinstance(new_generaldict[maimlelement.content],list) else [new_generaldict[maimlelement.content]]
            new_generaldict[maimlelement.content] = writeValue(generallist2,ciflist)

        key = new_generaldict[maimlelement.keyd]
        value = ''
        try:
            for cif in ciflist:
                cifkey = cif['keynum'].lstrip('_')
                u_value = ''
                if cifkey == key:
                    value = str(cif['value'])
                    floatpattern = r'^[-+]?[0-9]+(\.[0-9]+)?\(\d+\)$'
                    if re.match(floatpattern, value):
                        u_value = value.split('(')[1].replace(')','')
                        value = value.split('(')[0]
                    else:
                        value_converted = convert_list(value)
                        if value_converted:
                            value = value_converted
                        else:
                            value= value
                    
                    new_generaldict[maimlelement.value] = value
                
                    if u_value != '':
                        ## uncertaintyを作成
                        new_uncgenericdict = {}
                        new_uncgenericdict[maimlelement.keyd] = 'StandardDeviation'
                        new_uncgenericdict[maimlelement.typed] = 'doubleType'
                        u_formatstring, u_value= formatter_standarddeviation(value,u_value)
                        new_uncgenericdict[maimlelement.formatStringd] = str(u_formatstring)
                        new_uncgenericdict[maimlelement.value] = str(u_value)
                        
                        ## uncertaintyを追加
                        new_generaldict.update({maimlelement.uncertainty : new_uncgenericdict})
                    else:
                        pass
                    break
                            
            ##
            if value == None:
                #print("hit key:None::",key)
                new_generaldict[maimlelement.value] = ''
            
            #print(key, ":  ",value)
        except Exception as e:
            print(e)
            print("pass key=",key)
            new_generaldict[maimlelement.value] = ''
                
        new_generallist.append(new_generaldict) 
    return new_generallist


###########################################
## main method
###########################################
def main(maimlpath, ciffilepath, cifdicfilepath):
    ## 1. CIF
    ### 1-1. 読み込む
    cif_file = ReadCif(ciffilepath)
    
    ciflist = []
    # CIFファイルのすべてのデータブロックを取得
    for block_name in cif_file.keys():
        data_block = cif_file[block_name]
        # データブロック内のすべてのデータ項目とその値を取得
        for item in data_block.keys():
            value = data_block[item]
            ciflist.append({'keynum':str(item), 'value':str(value)})
        #print(ciflist)
        
    # CIF Fileの情報をテキストファイルに出力
    try:
        ciftxtpath = str(Path(filepath.tmp_dir + 'cif_output.txt'))
        with open(ciftxtpath, 'w', encoding='utf-8') as file:
            json.dump(ciflist, file) 
    except Exception as e:
        print("CIFファイルのテキスト出力に失敗: ",e)
        pass
            
    ## 2. MaiML
    ### 2-1. 読み込む
    maimldict = ''
    try:
        readWriteMaiML = ReadWriteMaiML()
        maimldict = readWriteMaiML.readFile(maimlpath)
    except Exception as e:
        print("MaiML file error.")
        raise e
        
    ### 2-2. 計測データを書き出すための準備
    #### 2-2-1. methodのID,programのID,instanceのIDを取得
    methoddict_ = maimldict[maimlelement.maiml][maimlelement.protocol][maimlelement.method]
    methodIDlist = methoddict_ if isinstance(methoddict_,list) else [methoddict_]
    
    for methoddict in methodIDlist:
        instprogIDdict__ = {}
        '''
            instprogIDdict = {'instructionID':{
                'programID':'',
                'methodID':'',
                },}
        '''
        ### 2-2-2. methoddictに含まれるinstructionのIDを取得し、instructionIDlistリストを作成
        programlist = methoddict[maimlelement.program] if isinstance(methoddict[maimlelement.program],list) else [methoddict[maimlelement.program]]
        for programdict in programlist:
            instructionlist = programdict[maimlelement.instruction] if isinstance(programdict[maimlelement.instruction],list) else [programdict[maimlelement.instruction]]
            for instructiondict in instructionlist:
                instprogIDdict__.update({
                    instructiondict[maimlelement.idd]:{
                    'programID':programdict[maimlelement.idd],
                    'methodID':methoddict[maimlelement.idd],
                }})
    
    ### 2-3. ファイルから取得したmaimlデータのprotocolからdata,eventLogの仮データを作成
    fullmaimldict = ''
    try:
        updateMaiML = UpdateMaiML()
        fullmaimldict = updateMaiML.createFullMaimlDict(maimldict) 
    except Exception as e:
        print("Error in UpdateMaiML-createFullMaimlDict.")
        raise e
    
    #### 2-3-1. results実データ作成の準備
    resultsdict__ = fullmaimldict[maimlelement.maiml][maimlelement.data].pop(maimlelement.results)
    resultslist__ = resultsdict__ if isinstance(resultsdict__, list) else [resultsdict__]  # 念の為

    #### 2-3-2. eventLog実データ作成の準備
    logdict__ = fullmaimldict[maimlelement.maiml][maimlelement.eventlog][maimlelement.log]
    loglist = logdict__ if isinstance(logdict__,list) else [logdict__]
    
    ## 本当は１つのresultsを特定すべきであるが、今回は１つしかないこと(=programが１つ)が前提(全てのresultsがVAMAS-block数分作成される)
    ## method IDを入力すること で対象となるresultsの特定が可能
    #for rindex, resultsdict1__ in enumerate(resultslist__):
    resultsdict1 = resultslist__[0]

    ### 2-3-3. instance内の汎用データコンテナを取得し更新
    instancelist = []
    materiallist = resultsdict1[maimlelement.material] if isinstance(resultsdict1[maimlelement.material],list) else [resultsdict1[maimlelement.material]]
    instancelist.extend(materiallist)
    conditionlist = resultsdict1[maimlelement.condition] if isinstance(resultsdict1[maimlelement.condition],list) else [resultsdict1[maimlelement.condition]]
    instancelist.extend(conditionlist)
    resultlist = resultsdict1[maimlelement.result] if isinstance(resultsdict1[maimlelement.result],list) else [resultsdict1[maimlelement.result]]
    instancelist.extend(resultlist)
    
    generallist = []
    for instancedict in instancelist:
        if maimlelement.property in instancedict:
            propertylist = instancedict[maimlelement.property] if isinstance(instancedict[maimlelement.property],list) else [instancedict[maimlelement.property]]
            generallist.extend(propertylist)
        if maimlelement.content in instancedict:
            contentlist = instancedict[maimlelement.content] if isinstance(instancedict[maimlelement.content],list) else [instancedict[maimlelement.content]]
            generallist.extend(contentlist)
    
    ### 2-3-3-2. results１つが持つ汎用データコンテナと、cifファイルのデータを比較
    try:
        generallist = writeValue(generallist, ciflist)
    except Exception as e:
        print("Error in generallist: ")
        raise e
    ## fullmaimldict[results]を、作成したresultslistで置き換える
    fullmaimldict[maimlelement.maiml][maimlelement.data].update({maimlelement.results:resultsdict1})

    
    
    ### 2-4. outputファイルを保存
    try:
        outmaimlpath = str(Path(filepath.output_dir + 'output.maiml'))
        path, duuid = readWriteMaiML.writecontents(fullmaimldict, outmaimlpath)
    except Exception as e:
        print('Error while writing to the file.')
        raise e
    
    return outmaimlpath



###########################################
## 実行関数
###########################################
if __name__ == '__main__':
    maimlfilename = "input.maiml"
    ciffilename = 'input.cif'
    maimlpath = ''
    ciffilepath = ''
    cifdicfilepath = 'INPUT/dictionaries/cif_core.dic'
    
    # inputファイルを取得
    if len(sys.argv) > 1:
        rootdir = Path(filepath.input_dir + sys.argv[1])
        if rootdir.exists() and rootdir.is_dir():
            cifcount = 0
            maimlcount = 0
            for file in rootdir.rglob('*'):  # rglob('*') で再帰的にすべてのファイルを取得
                if file.is_file():  # ファイルかどうかを確認
                    # ファイル名と拡張子を分けて取得
                    file_extension = file.suffix  # 拡張子を取得
                    if file_extension == '.maiml':
                        maimlfilename = file
                        maimlcount = maimlcount + 1
                    elif file_extension == '.cif':
                        ciffilename = file
                        cifcount = cifcount + 1
            if cifcount > 1 or maimlcount > 1:
                print('Error: More than one CIF or MAIML file found.')
                sys.exit()
            else:
                maimlpath = str(rootdir / maimlfilename)
                ciffilepath = str(rootdir / ciffilename)
    else:
        maimlpath = str(Path(filepath.input_dir + 'maiml/'+ maimlfilename))
        ciffilepath = str(Path(filepath.input_dir + 'CIF/'+ ciffilename))

    print('INPUT FILES ==')
    print('maimlpath: ',maimlpath)
    print('ciffilename: ',ciffilepath)
        
    try:        
        outputfilepath = main(maimlpath, ciffilepath, cifdicfilepath)
        print('Successfully created the data file.: ',outputfilepath)
    except Exception as e:
        print('Error : ',e)