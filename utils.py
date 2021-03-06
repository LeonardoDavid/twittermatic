import random

from datetime import date, datetime, timedelta

def datespan(startDate, endDate, delta=timedelta(days=1)):
    currentDate = startDate
    while currentDate < endDate:
        yield currentDate
        currentDate += delta

allTwitterDates = []       
for day in datespan(date(2006,3,21),date.today()+timedelta(days=30),delta=timedelta(days=30)):
    allTwitterDates.append(str(day))

allTwitterDatesByDay = []       
for day in datespan(date(2006,3,21),date.today()+timedelta(days=1),delta=timedelta(days=1)):
    allTwitterDatesByDay.append(str(day))

def convertCondensedNum(strnum):
    strnum = str(strnum)
    if 'K' in strnum:
        return int(1000 * float(strnum.split('K')[0]))
    elif 'M' in strnum:
        return int(1000000 * float(strnum.split('M')[0]))
    else:
        return int(strnum)


def randomTweet():
    C = 1
    fpath = 'data/tweet_corpus.txt'
    buffer = []

    f = open(fpath, 'r',encoding='utf8')
    for line_num, line in enumerate(f):
        line = line.encode('utf-8')
        n = line_num + 1.0
        r = random.random()
        if n <= C:
            buffer.append(line.strip())
        elif r < C/n:
            loc = random.randint(0, C-1)
            buffer[loc] = line.strip()
    
    words = []
    for word in buffer[0].split():
        word = word.decode("utf-8")
        if '#' not in word:
            words.append(word)
            
    tweet =' '.join(words).strip()
    if ('.' != tweet[-1] and
        '!' != tweet[-1] and
        '?' != tweet[-1]):
        tweet = tweet + '.'
    return tweet
