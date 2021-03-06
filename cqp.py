# -*- coding: utf-8 -*-

from flask import Flask, url_for, render_template, request
from collections import defaultdict,OrderedDict
from os.path import basename, splitext
from scipy.stats import hypergeom
from multiprocessing import Pool
from datetime import datetime
from CWB.CL import Corpus
import PyCQP_interface
import pandas as pd
import numpy as np
import random
import ujson
import datetime
import sys
import re
import os

def f(corpus,query):
    """
    Envoi de la requête à CQP et mise en forme des données récupérées
        entrée : nom du corpus sur lequel la requête sera effectuée et la requête en question
    """

    registry_dir="/usr/local/share/cwb/registry"
    #cqp=PyCQP_interface.CQP(bin='/usr/local/bin/cqp',options='-c -r '+registry_dir)
    cqp=PyCQP_interface.CQP(bin='/usr/local/cwb/bin//cqp',options='-c -r '+registry_dir)
    corpus_name=splitext(basename(corpus))[0].upper()
    dep=corpus_name.split("_")[1].upper()
    if (re.match(r"^\d$",dep)) :
        dep="0"+dep
    else :
        dep=dep

    resultDep = {}

    """
        Envoi de la requête
        Récupération des résultats, sous la forme d'une liste (results) qui contient autant de listes que de résultats correspondant à la requête effectuée, ou une liste vide si aucun résultat.
        Ces listes permettent de récupérer l'emplacement du premier et du dernier élément des motifs correspondants dans le corpus.
    """
    cqp.Exec(corpus_name+";")

    try :
        cqp.Query(query)
        rsize=int(cqp.Exec("size Last;"))
        results=cqp.Dump(first=0,last=20)
        #cqp.Exec("sort Last by word;")
        cqp.Terminate()
        # fermeture du processus CQP car sinon ne se ferme pas
        os.popen("kill -9 " + str(cqp.CQP_process.pid))

        resultDep[dep] = {"results":results, "nbTotalResults":rsize}

        return resultDep

    except Exception as e :
        return False

def specificities(freqMotifParDep) :
    """
        Calcule la spécificité du motif dans chaque département
            - entrée : dataframe contenant la fréquence du motif recherché par département
            - sortie : dictionnaire contenant pour chaque département la spécificité du motif
    """

    freqTot = 31868064
    freqTotParDep = pd.read_hdf('./static/freqByDep.hdf', 'freqTokensByDep')
    freqTotMotif = freqMotifParDep.sum().sum()
    df_freqTotMotif = pd.DataFrame(freqMotifParDep.sum(axis=1), columns=["0"])

    # Calcul de la fréquence attendue du motif dans chaque département
    expectedCounts = df_freqTotMotif.dot(freqTotParDep)/freqTot
    specif = freqMotifParDep.copy()

    """
        Pour chaque département, la spécificité du motif est calculée à partir de :
            - la fréquence du motif dans le département en question (à partir de freqMotifParDep)
            - la fréquence totale de tous les tokens (freqTot)
            - la fréquence totale du motif (freqTotMotif)
            - la fréquence totale de tous les tokens dans le département (à partir de freqTotParDep)
    """
    for dep in freqMotifParDep.columns :
        if (freqMotifParDep.loc["freq",dep]<expectedCounts.loc["freq",dep]) :
            specif.loc["freq",dep]=hypergeom.cdf(freqMotifParDep.loc["freq",dep], freqTot, freqTotMotif, freqTotParDep.transpose().loc[dep])
        else:
            specif.loc["freq",dep]=1-hypergeom.cdf(freqMotifParDep.loc["freq",dep]-1, freqTot, freqTotMotif, freqTotParDep.transpose().loc[dep])

    specif=np.log10(specif)
    specif[freqMotifParDep>=expectedCounts]=-specif[freqMotifParDep>=expectedCounts]

    # Les valeurs qui ne sont pas entre -10 et 10 sont tronquées
    for dep in specif :
        specif.loc[specif[dep] > 10,dep] = 10
        specif.loc[specif[dep] < -10,dep] = -10

    specif.rename(index={"freq":"specif"},inplace=True)
    specif = pd.DataFrame.to_dict(specif)

    return specif

# reconstitue les chaînes de caractères à partir d'une liste de tokens
def reconstituteString(tok_list) :
    no_space_before=[',','.',')',']']
    no_space_after=['(','[','\'']
    second=False
    reconstituted_string = ""
    for i,c in enumerate(tok_list) :
        if (i==len(tok_list)-1) :
            reconstituted_string+=c
        elif ((c=="'" or c=="\"")) :
            if (second==False) :
                reconstituted_string+=c
                second=True
            else :
                reconstituted_string+=c+" "
                second=False
        elif (tok_list[tok_list.index(c)+1]=="\"" or tok_list[tok_list.index(c)+1]=="'") :
            if (second) :
                reconstituted_string+=c
            else :
                reconstituted_string+=c+" "
        elif (tok_list[tok_list.index(c)+1] in no_space_before) :
            reconstituted_string+=c
        elif (c[-1] in no_space_after) :
            reconstituted_string+=c
        else :
            reconstituted_string+=c+" "
    return reconstituted_string

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/departements', methods=["POST"])
def getData():
    return render_template("departements.json")

"""
    Comportement lors de la réception d'une requête
    -----------------------------------------------
    Entrée -> requête
    Sortie -> dictionnaire contenant :
        - Un extrait des résultats obtenus pour le motif recherché (liste de dictionnaires ; un dictionnaire par résultat)
        - la spécificité du motif dans chaque département (dictionnaire)
"""
@app.route('/query', methods=["POST"])
def query():

    query=request.form["query"]+";"
    query_result=[]

    corpus_list = [("dep_1",query), ("dep_10",query), ("dep_11",query), ("dep_12",query), ("dep_13",query), ("dep_14",query), ("dep_15",query), ("dep_16",query), ("dep_17",query), ("dep_18",query), ("dep_19",query), ("dep_2",query), ("dep_21",query), ("dep_22",query), ("dep_23",query), ("dep_24",query), ("dep_25",query), ("dep_26",query), ("dep_27",query), ("dep_28",query), ("dep_29",query), ("dep_2a",query), ("dep_2b",query), ("dep_3",query), ("dep_30",query), ("dep_31",query), ("dep_32",query), ("dep_33",query), ("dep_34",query), ("dep_35",query), ("dep_36",query), ("dep_37",query), ("dep_38",query), ("dep_39",query), ("dep_4",query), ("dep_40",query), ("dep_41",query), ("dep_42",query), ("dep_43",query), ("dep_44",query), ("dep_45",query), ("dep_46",query), ("dep_47",query), ("dep_48",query), ("dep_49",query), ("dep_5",query), ("dep_50",query), ("dep_51",query), ("dep_52",query), ("dep_53",query), ("dep_54",query), ("dep_55",query), ("dep_56",query), ("dep_57",query), ("dep_58",query), ("dep_59",query), ("dep_6",query), ("dep_60",query), ("dep_61",query), ("dep_62",query), ("dep_63",query), ("dep_64",query), ("dep_65",query), ("dep_66",query), ("dep_67",query), ("dep_68",query), ("dep_69",query), ("dep_7",query), ("dep_70",query), ("dep_71",query), ("dep_72",query), ("dep_73",query), ("dep_74",query), ("dep_75",query), ("dep_76",query), ("dep_77",query), ("dep_78",query), ("dep_79",query), ("dep_8",query), ("dep_80",query), ("dep_81",query), ("dep_82",query), ("dep_83",query), ("dep_84",query), ("dep_85",query), ("dep_86",query), ("dep_87",query), ("dep_88",query), ("dep_89",query), ("dep_9",query), ("dep_90",query), ("dep_91",query), ("dep_92",query), ("dep_93",query), ("dep_94",query), ("dep_95",query)]

    # Ici, autant de processus qu'indiqués en argument de Pool vont se partager les tâches (récupérer pour chaque département le résultat de la requête cqp)

    #start_time = datetime.datetime.now()

    try :
        pool = Pool(processes=None)
        query_result = pool.starmap(f, corpus_list)
    finally:
        pool.close()
        pool.join()

    if query_result[0]==False :
        return "Erreur de syntaxe"

    else :
        allResults=[]

        freqParDepartement = defaultdict(int)
        # Construction d'un dataframe contenant la fréquence du motif recherché dans chaque département
        # récupération de l'ensemble des résultats dans une seule et même liste
        for depResult in query_result :
            for codeDep in depResult :
                freqParDepartement[codeDep]=depResult[codeDep]["nbTotalResults"]
                if depResult[codeDep]["results"]!=[['']] :
                    for result in depResult[codeDep]["results"] :
                        allResults.append({"dep":codeDep, "result":result})

        # calcul des spécificités
        freqParDepartementOrdered = OrderedDict(sorted(freqParDepartement.items(), key=lambda t: t[0]))
        df_queryFreq = pd.DataFrame(freqParDepartementOrdered, index=["freq"]).fillna(0)
        specif = specificities(df_queryFreq)

        resultsExtract = []
        registry_dir="/usr/local/share/cwb/registry"
        # Récupération des contextes gauche/droit + mise en forme, pour un extrait des résultats seulement (200 tirés au hasard)
        allResults_shuffle=[]
        random.shuffle(allResults)
        for i,dic in enumerate(allResults) :
            if i<200 :
                dep = dic["dep"]
                if (re.match(r"^0\d$",dep)) :
                    corpus_name = "dep_"+re.match(r"^0(\d)$",dep).group(1).lower()
                else :
                    corpus_name = "dep_"+dep.lower()

                r = dic["result"]

                corpus=Corpus(corpus_name,registry_dir=registry_dir);

                # permettra de récupérer par la suite le token, la POS ou le lemme correspondant à la position indiquée
                words=corpus.attribute("word","p")
                postags=corpus.attribute("pos","p")
                lemmas=corpus.attribute("lemma","p")

                sentences=corpus.attribute(b"text","s")

                left_context=[]
                right_context=[]
                start=int(r[0])
                end=int(r[1])

                # Récupération de la position du début et de la fin du tweet dans lequel le motif a été trouvé
                s_bounds=sentences.find_pos(end)

                # récupération de la position des mots des contextes droit et gauche
                for pos in range(s_bounds[0],s_bounds[1]+1) :
                    if (pos<start) :
                        left_context.append(pos)
                    if (pos>end) :
                        right_context.append(pos)

                # Construction du dictionnaire qui contiendra les informations qui nous intéressent
                result={"dep" : dep,
                        "hide_column" : "",
                        "left_context" : "",
                        "pattern" : "",
                        "right_context" : ""}

                lc_tokens = []
                lc_pos = []
                lc_lemmas = []
                rc_tokens = []
                rc_pos = []
                rc_lemmas = []

                # récupération du contexte gauche (tokens, pos et lemmes)
                for lp in left_context :
                    lc_tokens.append(words[lp])
                    lc_pos.append(postags[lp])
                    lc_lemmas.append(lemmas[lp])
                lc_tokens=reconstituteString(lc_tokens)
                lc_pos=" ".join(lc_pos)
                lc_lemmas=" ".join(lc_lemmas)

                # récupération du motif recherché (tokens, pos et lemmes)
                pattern_tokens=reconstituteString(words[start:end+1])
                pattern_pos=" ".join(postags[start:end+1])
                pattern_lemmas=" ".join(lemmas[start:end+1])

                # récupération du contexte droit (tokens, pos et lemmes)
                for rp in right_context :
                    rc_tokens.append(words[rp])
                    rc_pos.append(postags[rp])
                    rc_lemmas.append(lemmas[rp])
                rc_tokens=reconstituteString(rc_tokens)
                rc_pos=" ".join(rc_pos)
                rc_lemmas=" ".join(rc_lemmas)

                # mise en forme ici pour ne pas ajouter du temps de traitement côté client
                result["hide_column"]=lc_tokens[::-1]
                result["left_context"]="<span title=\""+lc_pos+"&#10;"+lc_lemmas+"\">"+lc_tokens+"</span>"
                result["pattern"]="<span title=\""+pattern_pos+"&#10;"+pattern_lemmas+"\">"+pattern_tokens+"</span>"
                result["right_context"]="<span title=\""+rc_pos+"&#10;"+rc_lemmas+"\">"+rc_tokens+"</span>"

                resultsExtract.append(result)

        #print(datetime.datetime.now()-start_time)

        resultAndSpec = {}
        resultAndSpec["result"]=resultsExtract
        resultAndSpec["specif"]=specif
        resultAndSpec["nbResults"]=int(df_queryFreq.sum().sum())
        resultAndSpec["nbOccurrences"]=freqParDepartement
        resultAndSpec=ujson.dumps(resultAndSpec)

        return resultAndSpec
