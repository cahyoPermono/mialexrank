import requests
import pprint
import datefinder
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, request, redirect
import os
import shutil
from lexrank import STOPWORDS, LexRank
from path import Path

app = Flask(__name__)


@app.route('/')
def mia_home():
    return redirect('/scrapping')


@app.route('/lexrank', methods=['GET', 'POST'])
def mia_lexranknew():
    if request.method == 'GET':
        return render_template('lexrank_form.html')
    elif request.method == 'POST':
        dataForm = request.form.to_dict()

        data = getDataFromBeberapaBerita(dataForm)

        return render_template('lexrank_submit.html', data=data)


@app.route('/scrapping', methods=['GET', 'POST'])
def mia_scrapping():
    if request.method == 'POST':
        data = request.form.to_dict()

        tglMulai = '28/10/2020'
        tglSelesai = '28/10/2020'
        kategori = 'politik'

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

    for xc in range(int(dataForm['cnnindonesia'])):
        pathFileC = './db/'+'cnnindonesia.com'+str(xc)+'.txt'
        with open(pathFileC, mode='r') as cnnFile:
            content = cnnFile.read().splitlines()
            isiContent = ' '.join(map(str, content[2:]))
            listBerita.append({
                'judul': content[0],
                'isiBerita': isiContent,
                'sumber': 'cnnindonesia.com',
                'modalId': 'cnnindonesiacom'+str(xc)
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
    tglMulai = next(datefinder.find_dates(tglMulaiString), None)
    tglSelesai = next(datefinder.find_dates(tglSelesaiString), None)

    listObjectDetik = []

    dalamJangkauan = True

    while dalamJangkauan:
        # get berita dari detik
        resDetik = requests.get(
            'https://www.detik.com/search/searchall?query='+keyword+'&siteid=2&sortby=time&page=+'+str(pages))
        soupDetik = BeautifulSoup(resDetik.text, 'html.parser')
        articleDetiks = soupDetik.select('article')
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
            dateDetikString = articleDetik.select('.date')[0].getText()
            # convert jadi object datetime biar bisa di bandingkan
            dateDetik = next(datefinder.find_dates(dateDetikString), None)

            # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
            if dateDetik > tglSelesai:
                continue

            # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
            if dateDetik < tglMulai:
                dalamJangkauan = False

            objectDetik = {
                "link": articleDetik.select('a')[0].get('href'),
                "judul": articleDetik.select('a')[0].select('h2')[0].getText(),
                "sumber": "detik.com"
            }

            listObjectDetik.append(objectDetik)
        pages += 1

    # get berita dari cnn
    listObjectCnn = []
    resCnn = requests.get(
        'https://www.cnnindonesia.com/search/?query='+keyword)
    soupCnn = BeautifulSoup(resCnn.text, 'html.parser')
    # articleCnn = soupCnn.select('.list')[0].select('article')[0]
    articleCnns = soupCnn.select('.list')[0].select('article')

    for articleCnn in articleCnns:
        objectCnn = {
            "link": articleCnn.select('a')[0].get('href'),
            "judul": articleCnn.select('a')[0].select('h2')[0].getText(),
            "sumber": "cnnindonesia.com"
        }

        listObjectCnn.append(objectCnn)
    
    # get berita dari jpnn.com
    listObjectJpnn = []

    # ganti spasi keyword karena di jpnn g bisa pakai + untuk spasinya
    keywordJpnn = keyword.replace("+", "-")

    resJpnn = requests.get(
        'https://www.jpnn.com/tag/'+keywordJpnn+'?page='+str(pages))
    soupJpnn = BeautifulSoup(resJpnn.text, 'html.parser')

    articleJpnns = soupJpnn.select('.content-description')

    for articleJpnn in articleJpnns:
        pprint.pprint(articleJpnn)
        pprint.pprint('====')
        # objectCnn = {
        #     "link": articleCnn.select('a')[0].get('href'),
        #     "judul": articleCnn.select('a')[0].select('h2')[0].getText(),
        #     "sumber": "cnnindonesia.com"
        # }

        # listObjectCnn.append(objectCnn)

    # get berita dari Antara
    listObjectAntara = []
    pages = 1
    dalamJangkauan = True
    while dalamJangkauan:

        resAntara = requests.get(
            'https://www.antaranews.com/search/'+keyword+'/'+str(pages))
        soupAntara = BeautifulSoup(resAntara.text, 'html.parser')
        # articleAntara = soupAntara.select(".post-content.clearfix article h3")[0]
        articleAntaras = soupAntara.select(".post-content.clearfix article")

        for articleAntara in articleAntaras:
            # mapping category karena tiap portal berita nama kategorinya berbeda beda
            userCategory = mappingCategory('antaranews.com', category)

            # get kategori dari artikel di antaranews
            antaraCategory = articleAntara.select('p a')[0].getText()

            # kalauu kategori tidak sama lanjut loopingan selanjutnya
            if antaraCategory != userCategory:
                continue

            antaraDate = articleAntara.select('p span')[0].getText()
            antaraDate = next(datefinder.find_dates(antaraDate), None)

            # cek kalau tanggal berita tidak lebih baru dari jangka waktu yang ditentukan
            if antaraDate > tglSelesai:
                continue

            # cek kalau tanggal berita lebih lama dari yang ditentukan stop looping berita
            if antaraDate < tglMulai:
                dalamJangkauan = False

            objectAntara = {
                "link": articleAntara.select('h3 a')[0].get('href'),
                "judul": articleAntara.select('h3 a')[0].getText(),
                "sumber": "antaranews.com"
            }

            listObjectAntara.append(objectAntara)
        pages += 1

    list = {"detik": listObjectDetik, "cnn": listObjectCnn,
            "antaranews": listObjectAntara}
    return list


def mappingCategory(sumber, category):
    if(sumber == 'detik.com'):
        if category == 'politik':
            return 'detikNews'
    elif(sumber == 'antaranews.com'):
        if category == 'politik':
            return 'Politik'


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
                        with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myDetikFile:
                            myDetikFile.write(parag.getText() + '\n')
                    except IOError as err:
                        raise err

            elif article['sumber'] == 'cnnindonesia.com':
                # save Judul to db
                try:
                    with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myCnnFile:
                        myCnnFile.write(article['judul'] + '\n\n')
                except IOError as err:
                    raise err

                articleCnn = soupArticle.select(
                    "#detikdetailtext p")

                for parag in articleCnn:
                    # save content paragraph to db
                    try:
                        with open('./db/'+article['sumber']+str(idxArticle)+'.txt', mode='a') as myCnnFile:
                            myCnnFile.write(parag.getText() + '\n')
                    except IOError as err:
                        raise err

            if article['sumber'] == 'antaranews.com':
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
