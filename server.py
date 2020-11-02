import requests
import pprint
import http.client
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, request, redirect
import os
import shutil
from lexrank import STOPWORDS, LexRank
from path import Path
import fnmatch
from dateparser.search import search_dates

app = Flask(__name__)

# biar g error pas ambil antaranews
http.client._MAXHEADERS = 1000


@app.route('/')
def mia_home():
    return redirect('/scrapping')


@app.route('/lexrank', methods=['GET', 'POST'])
def mia_lexranknew():
    if request.method == 'GET':
        detikLen = len(fnmatch.filter(os.listdir('./db'), 'detik*.txt'))
        antaraLen = len(fnmatch.filter(os.listdir('./db'), 'antara*.txt'))
        cnbcLen = len(fnmatch.filter(os.listdir('./db'), 'cnbc*.txt'))
        return render_template('lexrank_form.html', detikLen=detikLen, antaraLen=antaraLen, cnbcLen=cnbcLen)
    elif request.method == 'POST':
        dataForm = request.form.to_dict()

        data = getDataFromBeberapaBerita(dataForm)

        return render_template('lexrank_submit.html', data=data)


@app.route('/scrapping', methods=['GET', 'POST'])
def mia_scrapping():
    if request.method == 'POST':
        data = request.form.to_dict()
        tglMulai = data['tglMulai']
        tglSelesai = data['tglAkhir']
        kategori = data['category']

        # dapetin list berita yang ada di portal berita
        data["listBerita"] = getDataBerita(
            data["keyword"].replace(" ", "+"), tglMulai, tglSelesai, kategori)

        # dapetin full artikelnya lalu dimasukin ke db
        saveArticleFromListBerita(data["listBerita"])

        return render_template('scrapping_submit.html', data=data)

    elif request.method == 'GET':
        return render_template('scrapping_form.html')


def getDataFromBeberapaBerita(dataForm):
    listBerita = []
    sentences = []

    for xd in range(int(dataForm['detik'])):
        pathFileD = './db/'+'detik.com'+str(xd)+'.txt'
        with open(pathFileD, mode='r') as detikFile:
            content = detikFile.read().splitlines()
            isiContent = ' '.join(map(str, content[2:]))
            listBerita.append({
                'judul': content[0],
                'isiBerita': isiContent,
                'sumber': 'detik.com',
                'modalId': 'detikcom'+str(xd)
            })
            sentences.extend(content[2:])

    for xc in range(int(dataForm['cnbc'])):
        pathFileC = './db/'+'cnbcindonesia.com'+str(xc)+'.txt'
        with open(pathFileC, mode='r') as cnbcFile:
            content = cnbcFile.read().splitlines()
            isiContent = ' '.join(map(str, content[2:]))
            listBerita.append({
                'judul': content[0],
                'isiBerita': isiContent,
                'sumber': 'cnbcindonesia.com',
                'modalId': 'cnbcindonesiacom'+str(xc)
            })
            sentences.extend(content[2:])

    for xa in range(int(dataForm['antaranews'])):
        pathFileA = './db/'+'antaranews.com'+str(xa)+'.txt'
        with open(pathFileA, mode='r') as antaraFile:
            content = antaraFile.read().splitlines()
            isiContent = ' '.join(map(str, content[2:]))
            listBerita.append({
                'judul': content[0],
                'isiBerita': isiContent,
                'sumber': 'antaranews.com',
                'modalId': 'antaranewscom'+str(xa)
            })
            sentences.extend(content[2:])

    # Bersihkan Sentences Dari empty string
    cleanSentences = [string for string in sentences if string != ""]
    cleanSentences2 = [string for string in cleanSentences if string != " "]

    # get Resume berita
    resumeBerita = getResume(
        cleanSentences2, dataForm['summary'], float(dataForm['threshold']))

    data = {
        'listBerita': listBerita,
        'sentences': sentences,
        'resumeBerita': resumeBerita,
        'jumlahBerita': len(listBerita)
    }

    return data


def getResume(sentences, summary_size, threshold):
    documents = []
    documents_dir = Path('./db')
    stopwords = {}
    stopwords_dir = Path('./static/stopwords-id.txt')

    for file_path in documents_dir.files('*.txt'):
        with file_path.open(mode='rt', encoding='utf-8', errors='ignore') as fp:
            documents.append(fp.readlines())

    # get the stpwords
    with stopwords_dir.open(mode='rt', encoding='utf-8') as stopFile:
        stopwords['id'] = set(stopFile.readlines())
        stopFile.close()

    lxr = LexRank(documents, stopwords=stopwords['id'])

    summary = lxr.get_summary(sentences, summary_size=int(
        summary_size), threshold=threshold)

    return summary


def getDataBerita(keyword, tglMulaiString, tglSelesaiString, category):

    pages = 1
    tglMulai = search_dates(tglMulaiString)[0][1]
    tglSelesai = search_dates(tglSelesaiString)[0][1]

    listObjectDetik = []

    dalamJangkauan = True

    while dalamJangkauan:
        # get berita dari detik
        resDetik = requests.get(
            'https://www.detik.com/search/searchall?query='+keyword+'&siteid=2&sortby=time&page=+'+str(pages))
        soupDetik = BeautifulSoup(resDetik.text, 'html.parser')
        articleDetiks = soupDetik.select('article')

        # print("Detik")
        # print(pages)

        if len(articleDetiks) == 0:
            dalamJangkauan = False

        for articleDetik in articleDetiks:
            # mapping category karena tiap portal berita nama kategorinya berbeda beda
            userCategory = mappingCategory('detik.com', category)

            detikCategory = articleDetik.select('.category')[0].getText()

            # kalauu kategori tidak sama lanjut loopingan selanjutnya
            if detikCategory != userCategory:
                continue

            # remove category agar bisa dapat data tanggal
            articleDetik.select('.date')[0].select('span')[0].decompose()

            # get date article
            dateDetikString = articleDetik.select(
                '.date')[0].getText().split(',')[1]
            dateDetikString = dateDetikString[1:12]
            dateDetik = search_dates(dateDetikString)[0][1]

            # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
            if dateDetik > tglSelesai:
                continue

            # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
            if dateDetik < tglMulai:
                dalamJangkauan = False
                break

            objectDetik = {
                "link": articleDetik.select('a')[0].get('href'),
                "judul": articleDetik.select('a')[0].select('h2')[0].getText(),
                "tglBerita": dateDetikString,
                "sumber": "detik.com"
            }

            listObjectDetik.append(objectDetik)
        pages += 1

    # get berita dari cnn
    # listObjectCnn = []
    # resCnn = requests.get(
    #     'https://www.cnnindonesia.com/search/?query='+keyword)
    # soupCnn = BeautifulSoup(resCnn.text, 'html.parser')
    # # articleCnn = soupCnn.select('.list')[0].select('article')[0]
    # articleCnns = soupCnn.select('.list')[0].select('article')

    # for articleCnn in articleCnns:
    #     objectCnn = {
    #         "link": articleCnn.select('a')[0].get('href'),
    #         "judul": articleCnn.select('a')[0].select('h2')[0].getText(),
    #         "sumber": "cnnindonesia.com"
    #     }

    #     listObjectCnn.append(objectCnn)

    # get berita dari jpnn.com
    # listObjectJpnn = []
    # pages = 1
    # dalamJangkauan = True
    # dateJpnn = tglSelesai
    # while dalamJangkauan:
    #     # ganti spasi keyword karena di jpnn g bisa pakai + untuk spasinya
    #     keywordJpnn = keyword.replace("+", "-")

    #     resJpnn = requests.get(
    #         'https://www.jpnn.com/tag/'+keywordJpnn+'?page='+str(pages))
    #     soupJpnn = BeautifulSoup(resJpnn.text, 'html.parser')

    #     # print("Jpnns")
    #     # print(pages)

    #     articleJpnns = soupJpnn.select('.content-description')
    #     if len(articleJpnns) == 0:
    #         dalamJangkauan = False
    #     for articleJpnn in articleJpnns:

    #         # mapping category karena tiap portal berita nama kategorinya berbeda beda
    #         userCategory = mappingCategory('jpnn.com', category)

    #         jpnnCategory = articleJpnn.select('h6 strong')[0].getText()

    #         # print(userCategory)
    #         # print(jpnnCategory)

    #         # kalauu kategori tidak sama lanjut loopingan selanjutnya
    #         if jpnnCategory != userCategory:
    #             continue

    #         # get date article
    #         dateJpnnString = articleJpnn.select('h6 span')[0].getText()

    #         # print(dateJpnn)
    #         # print(search_dates(articleJpnn.select('h6 span')[0].getText().split(',')[1])[0][1])
    #         # print(dateJpnn < search_dates(articleJpnn.select('h6 span')[0].getText().split(',')[1])[0][1])
    #         # print(tglMulai)
    #         # print(tglSelesai)

    #         # cek perulangan khusus jpnn
    #         if dateJpnn < search_dates(articleJpnn.select('h6 span')[0].getText().split(',')[1])[0][1]:
    #             dalamJangkauan = False
    #             break

    #         # convert jadi object datetime biar bisa di bandingkan
    #         dateJpnn = search_dates(articleJpnn.select('h6 span')[
    #                                 0].getText().split(',')[1])[0][1]

    #         # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
    #         if dateJpnn > tglSelesai:
    #             continue

    #         # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
    #         if dateJpnn < tglMulai:
    #             dalamJangkauan = False
    #             continue

    #         objectJpnn = {
    #             "link": articleJpnn.select('h1 a')[0].get('href'),
    #             "judul": articleJpnn.select('h1 a')[0].get('title'),
    #             "tglBerita": dateJpnnString,
    #             "sumber": "jpnn.com"
    #         }

    #         listObjectJpnn.append(objectJpnn)
    #     pages += 1

    # get berita dari Antara
    listObjectAntara = []
    pages = 1
    dalamJangkauan = True
    while dalamJangkauan:

        resAntara = requests.get(
            'https://www.antaranews.com/search/'+keyword+'/'+str(pages))
        soupAntara = BeautifulSoup(resAntara.text, 'html.parser')

        # print("Antara")
        # print(pages)
        # articleAntara = soupAntara.select(".post-content.clearfix article h3")[0]
        articleAntaras = soupAntara.select(".post-content.clearfix article")

        if len(articleAntaras) == 0:
            dalamJangkauan = False

        for articleAntara in articleAntaras:
            # mapping category karena tiap portal berita nama kategorinya berbeda beda
            userCategory = mappingCategory('antaranews.com', category)

            # get kategori dari artikel di antaranews
            antaraCategory = articleAntara.select('p a')[0].getText()

            # kalauu kategori tidak sama lanjut loopingan selanjutnya
            if antaraCategory != userCategory:
                continue

            antaraDateString = articleAntara.select('p span')[0].getText()
            antaraDate = search_dates(antaraDateString.lstrip())[0][1]

            # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
            if antaraDate > tglSelesai:
                continue

            # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
            if antaraDate < tglMulai:
                dalamJangkauan = False
                continue

            objectAntara = {
                "link": articleAntara.select('h3 a')[0].get('href'),
                "judul": articleAntara.select('h3 a')[0].getText(),
                "tglBerita": antaraDate,
                "sumber": "antaranews.com"
            }

            listObjectAntara.append(objectAntara)
        pages += 1

    # get berita dari cnbcindonesia
    listObjectCnbcindonesia = []
    pages = 1
    dalamJangkauan = True

    while dalamJangkauan:
        # get berita dari detik
        resCnbcindonesia = requests.get(
            'https://www.cnbcindonesia.com/search?query='+keyword+'&p='+str(pages)+'&kanal=&tipe=&date=')
        soupCnbcindonesia = BeautifulSoup(resCnbcindonesia.text, 'html.parser')
        articleCnbcindonesias = soupCnbcindonesia.select(
            '.list.media_rows.middle.thumb.terbaru.gtm_indeks_feed')[0].select('article')

        print("cnbc")
        print(pages)
        if len(articleCnbcindonesias) == 0:
            dalamJangkauan = False

        for articleCnbcindonesia in articleCnbcindonesias:
            # mapping category karena tiap portal berita nama kategorinya berbeda beda
            userCategory = mappingCategory('cnbcindonesia.com', category)
            judulCnbc = articleCnbcindonesia.select('a div h2')[0].getText()
            cnbcIndonesiaCategory = articleCnbcindonesia.select('a div span span')[
                0].getText()

            print(userCategory)
            print(cnbcIndonesiaCategory)

            # kalauu kategori tidak sama lanjut loopingan selanjutnya
            if cnbcIndonesiaCategory != userCategory:
                continue

            # get date article
            resCnbcForDate = requests.get(
                articleCnbcindonesia.select('a')[0].get('href'))
            soupCnbcForDate = BeautifulSoup(resCnbcForDate.text, 'html.parser')
            dateCnbcString = soupCnbcForDate.select('.date')[0].getText()
            dateCnbc = search_dates(dateCnbcString)[0][1].replace(hour=0, minute=0, second=0, microsecond=0)

            print(dateCnbcString)
            print(dateCnbc)
            print(tglSelesai)
            print(tglMulai)
            print(dateCnbc > tglSelesai)
            print(dateCnbc < tglMulai)
            # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
            if dateCnbc > tglSelesai:
                continue

            # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
            if dateCnbc < tglMulai:
                dalamJangkauan = False
                break
            
            print('masuk 1')
            objectCnbcIndonesia = {
                "link": articleCnbcindonesia.select('a')[0].get('href'),
                "judul": judulCnbc,
                "tglBerita": dateCnbcString,
                "sumber": "cnbcindonesia.com"
            }

            listObjectCnbcindonesia.append(objectCnbcIndonesia)
        print(listObjectCnbcindonesia)
        pages += 1

    list = {"detik": listObjectDetik, "cnn": listObjectCnn,
            "antaranews": listObjectAntara, "jpnn": listObjectJpnn, "cnbc": listObjectCnbcindonesia}
    return list


def mappingCategory(sumber, category):
    if(sumber == 'detik.com'):
        if category == 'politik':
            return 'detikNews'
        elif category == 'sports':
            return 'detikSport'
        elif category == 'teknologi':
            return 'detikInet'
    elif(sumber == 'antaranews.com'):
        if category == 'politik':
            return 'Politik'
        elif category == 'sports':
            return 'Olahraga'
        elif category == 'teknologi':
            return 'Tekno'
    elif(sumber == 'jpnn.com'):
        if category == 'politik':
            return 'Politik'
        elif category == 'sports':
            return 'Olahraga'
        elif category == 'teknologi':
            return 'Teknologi'
    elif(sumber == 'cnbcindonesia.com'):
        if category == 'politik':
            return 'News'
        elif category == 'teknologi':
            return 'Tech'
        elif category == 'sports':
            return 'Lifestyle'


def saveArticleFromListBerita(listBerita):
    deleteAllFiles()
    for portal in listBerita:
        for idxArticle, article in enumerate(listBerita[portal]):
            resArticle = requests.get(article["link"])
            soupArticle = BeautifulSoup(resArticle.text, 'html.parser')

            if article['sumber'] == 'detik.com':
                # save Judul to db
                try:
                    with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myDetikFile:
                        myDetikFile.write(article['judul'] + '\n\n')
                except IOError as err:
                    raise err

                articleDetik = soupArticle.select(
                    ".detail__body-text.itp_bodycontent p")
                for parag in articleDetik:
                    if parag.find(class_='detail__long-nav'):
                        continue

                    # save content paragraph to db
                    try:
                        with open('./db/'+article['sumber']+str(idxArticle)+'.txt', encoding="utf-8", mode='a') as myDetikFile:
                            myDetikFile.write(parag.getText() + '\n')
                    except IOError as err:
                        raise err

            # elif article['sumber'] == 'cnnindonesia.com':
            #     # save Judul to db
            #     try:
            #         with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myCnnFile:
            #             myCnnFile.write(article['judul'] + '\n\n')
            #     except IOError as err:
            #         raise err

            #     articleCnn = soupArticle.select(
            #         "#detikdetailtext p")

            #     for parag in articleCnn:
            #         # save content paragraph to db
            #         try:
            #             with open('./db/'+article['sumber']+str(idxArticle)+'.txt', encoding="utf-8", mode='a') as myCnnFile:
            #                 myCnnFile.write(parag.getText() + '\n')
            #         except IOError as err:
            #             raise err

            elif article['sumber'] == 'antaranews.com':
                # save Judul to db
                try:
                    with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myAntaraFile:
                        myAntaraFile.write(article['judul'] + '\n\n')
                except IOError as err:
                    raise err

                articleAntara = soupArticle.select(
                    ".post-content.clearfix")

                # remove br element
                if(articleAntara):
                    for tag in articleAntara[0].select("br, div, script, span, p, ins"):
                        tag.decompose()

                # save content paragraph to db
                try:
                    with open('./db/'+article['sumber']+str(idxArticle)+'.txt', encoding="utf-8", mode='a') as myAntaraFile:
                        myAntaraFile.write(articleAntara[0].getText())
                except IOError as err:
                    raise err

            # elif article['sumber'] == 'jpnn.com':
            #     # save Judul to db
            #     try:
            #         with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myCnnFile:
            #             myCnnFile.write(article['judul'] + '\n\n')
            #     except IOError as err:
            #         raise err

            #     articleJnn = soupArticle.select(".page-content p")

            #     for parag in articleJnn:
            #         # save content paragraph to db
            #         try:
            #             with open('./db/'+article['sumber']+str(idxArticle)+'.txt', encoding="utf-8", mode='a') as myCnnFile:
            #                 myCnnFile.write(parag.getText() + '\n')
            #         except IOError as err:
            #             raise err
            
            elif article['sumber'] == 'cnbcindonesia.com':
                # save Judul to db
                try:
                    with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myCnbcFile:
                        myCnbcFile.write(article['judul'] + '\n\n')
                except IOError as err:
                    raise err

                articleCnbc = soupArticle.select(
                    ".detail_text p")

                pprint.pprint(articleCnbc)
                for parag in articleCnbc:

                    for tag in parag.select("br, div, strong, a, p, ins"):
                        tag.decompose()

                    # save content paragraph to db
                    try:
                        with open('./db/'+article['sumber']+str(idxArticle)+'.txt', encoding="utf-8", mode='a') as mycnbcFile:
                            mycnbcFile.write(parag.getText() + '\n')
                    except IOError as err:
                        raise err


def deleteAllFiles():
    folder = './db'
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
