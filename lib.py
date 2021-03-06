"""YATA

This is a true twitter bot that makes it easy to
make friends, and bulk follow-back or unfollow people.

WITH GREAT POWER COMES GREAT RESPONSIBILITY.

Try not to abuse this script. Check the config.json file for
parameters that change how aggressive this bot will try to
make friends.

Notes:

- When you reach 2,000 followers, you will not be able to add any more.
  Currently this script doesn't ever check how many followers you have,
  so it will just keep trucking even though it won't be following people
  after 2,000. When you reach 2,000 just run twitterbot.py unfollow to
  get rid of folks.

- There are random sleeps throughout the script to make it "look"
  more like a real person is interacting with the site.

"""

import random
import json
import os
import re
import logging
from os import walk
from time import sleep, time
import traceback

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime, timedelta
import praw

import utils
import data.database as database
import data.database_commands as database_commands

# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='twitterbot.log',
                    filemode='w')
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)
selenium_logger = logging.getLogger(
    'selenium.webdriver.remote.remote_connection')
# Only display possible problems
selenium_logger.setLevel(logging.WARN)



class TwitterBot(object):

    """TwitterBot object

    Public Methods:

    signin()              -   Signs in the user
    screenshot()          -   Takes screen shot
    unfollow()            -   Unfollows in bulk
    followback()          -   Follow back in bulk
    collectTweets(handle) -   Collects tweets for the given handle
    liveSearch(term)      -   Loads all the tweets that match search term
    loadEntireFeed()      -   After doing a search, this can be used to load the entire feed
    processFeed()         -   After using liveSearch(term) you can use this to process the tweets in feed
    makefriends()         -   Follow/Favorite/Reply/Retweet in bulk using search terms
                                (does liveSearch + loadEntireFeed + processFeed)
    tweet(text)           -   Tweets the given text
    generateTweet()       -   Generates a tweet from the corpus
    logout()              -   Signs out and closes down driver
    """

    def __init__(self, settingsFile, tor=False,headless=False):
        """ Initialize Twitter bot

            @param settingsFiles    {String} name of settings file
            @param tor              {Boolean} whether to use tor
        """
        database.init_db()
        self.settings = json.load(open(settingsFile, 'r'))
        self.settings['file'] = settingsFile
        self.tor = tor
        self.logger = logging.getLogger(self.settings['file'])
        self.signedIn = False
        self.phantom = False
        self.headless = headless
        self.twittername = self.settings['twittername']
        self.logger.debug('Initialized')

    def signin(self):
        """ Signs in user

            Loads the driver and signs in.
            After signing in it gets new data
        """
        self.logger.debug('Signing in...')

        if self.headless:
            self.driver = None
            files = []
            for root, dirnames, filenames in os.walk('./drivers/'):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            for pfile in files:
                try:
                    self.driver = webdriver.PhantomJS(executable_path=pfile, service_log_path="phantomjs.log")
                    self.logger.info('Using phantomJS driver: ' + pfile)
                    self.phantom = True
                except:
                    self.driver = None
                if self.driver is not None:
                    break
            if self.driver is None:
                self.phantom = False
                self.logger.error('Problem loading driver')
                self.profile = webdriver.FirefoxProfile()
                self.driver = webdriver.Firefox(self.profile)
        else:
            self.phantom = False
            self.profile = webdriver.FirefoxProfile()
            self.driver = webdriver.Firefox(self.profile)

        user = self.settings['username']
        psw = self.settings['password']

        if self.tor:
            self.logger.debug('Using TOR')
            profile.set_preference('network.proxy.type', 1)
            profile.set_preference('network.proxy.socks', '127.0.0.1')
            profile.set_preference('network.proxy.socks_port', 9050)

        # sign-in
        self.driver.get("http://www.twitter.com")
        sleep(1)

        # Log in is the button in the upper right in this case
        css = '.' + 'Button StreamsLogin js-login'.replace(' ', ',')
        login_buttons = self.driver.find_elements(By.CSS_SELECTOR, css)
        loginSuccess = False
        try:
            if len(login_buttons) > 0:
                self.logger.debug('Using login method 1')
                for button in login_buttons:
                    if "log" in button.text.lower():
                        button.click()
                        sleep(0.1)
                elems = self.driver.find_elements(
                    By.CSS_SELECTOR, '.text-input')
                elems[0].send_keys(user)
                sleep(0.1)
                elems[1].send_keys(psw + Keys.RETURN)
                loginSuccess = True
        except:
            pass
        if not loginSuccess:
            try:
                self.logger.debug('Using login method 2')
                eleme = self.driver.find_element_by_css_selector(
                    '.front-signin.js-front-signin')
                elem = eleme.find_element_by_css_selector(
                    '.text-input.email-input')
                elem.send_keys(user)
                elem = eleme.find_element_by_css_selector(
                    '.text-input.flex-table-input')
                elem.send_keys(psw + Keys.RETURN)
                loginSuccess = True
            except:
                pass
        if not loginSuccess:
            self.logger.error('No login method has worked!')
        self.logger.debug(self.driver.current_url)
        self.signedIn = loginSuccess
        self._getStats()



    def screenshot(self, filename=None):
        """ Takes a screenshot.

            @param filename     {String} filename for screenshot
        """
        self.logger.info("Taking a screenshot")
        if not filename:
            filename = str(time())
        if '.png' not in filename:
            filename += '.png'
        savefile = os.path.join('screenshots', filename)
        self.driver.save_screenshot(savefile)

    def unfollow(self):
        """ Unfollow in bulk

            Goes to following page and unfollows 60% of followers,
            skipping the first 600.
        """
        logger = logging.getLogger('lib.unfollow')
        if not self.signedIn:
            self.signin()

        logger.info('unfollowing...')
        self.driver.get(
            "http://www.twitter.com/" + self.settings['twittername'] + '/following')
        for i in range(60):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            sleep(.2)
        logger.info('finished loading')
        skip = 0
        blocks = self.driver.find_elements(
            By.CSS_SELECTOR, ".Grid-cell.u-size1of2.u-lg-size1of3.u-mb10")
        for block in blocks:
            text = str(block.text.encode('ascii', 'ignore'))
            logger.debug(text)
            skip += 1
            if 'FOLLOWS YOU' not in text and skip > 200:
                css = '.' + \
                    'user-actions-follow-button js-follow-btn follow-button btn small small-follow-btn'.replace(
                        ' ', '.')
                button = block.find_elements(By.CSS_SELECTOR, css)[0]
                button.click()

        self.logger.debug(self.driver.current_url)
        self._getStats()

    def makefriends(self):
        """ Follow/Favorite/Retweet/Reply in bulk

            Searches for specified search terms (in configuration)
            Goes through tweets and follows/favorites/retweets/replies
            based on probabilities
        """
        logger = logging.getLogger('lib.makefriends')
        if not self.signedIn:
            self.signin()

        if self.settings['following'] > 1900:
            self.unfollow()

        # Generate search terms
        search_expressions = self.settings['search_expressions']
        avoid_words = self.settings['avoid_words']
        search_avoid_words = self.settings['search_avoid_words']

        search_terms = []
        for exp in search_expressions:
            search_terms.append('"' + exp + '" ' + '-' + ' -'.join(search_avoid_words) + ' since:' + (datetime.now() - timedelta(
                days=2)).strftime("%Y-%m-%d") + ' until:' + (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))

        for search_term in search_terms:
            logger.info(
                'Seeking out [' + search_term + '] for ' + self.settings['twittername'])
            self.liveSearch(search_term)
            logger.debug('Loading all tweets')
            self.tweetboxes = self._loadAllTweets(numTimes=20)
            logger.debug('Processing feed')
            self.processFeed()

    def _loadAllTweets(self, numTimes=10000):
        """ Loads all the available tweets

            When searching or loading feed, you can use this function
            load tweets by continuing scrolling to the bottom until no
            more tweets load (or numTimes reached)

            @param numTimes     {Integer} number of times to scroll??
        """
        lastNum = 0
        newNum = 1
        num = 0
        while lastNum != newNum and num < numTimes:
            if not self.phantom:
                '''
                self.driver.execute_script('$("body").scrollTop(10000000);')
                sleep(.25)
                self.driver.execute_script('$("html, body").animate({scrollTop: 10000},"slow");')
                sleep(.25)
                '''
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(.25)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(.25)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(.25)
            lastNum = newNum
            tweetboxes = self.driver.find_elements(By.CSS_SELECTOR,
                                                   ".js-stream-item.stream-item.stream-item.expanding-stream-item")
            num += 1
            newNum = len(tweetboxes)

        return tweetboxes

    def loadEntireFeed(self):
        """Loads an entire feed, be careful this could take awhile sometimes"""

        self.tweetboxes = self._loadAllTweets()

    def saveTwitterHandle(self,twitterhandle):
        self.driver.get("http://www.twitter.com/" + twitterhandle)
        name = self.driver.find_element(By.CSS_SELECTOR,"a.ProfileHeaderCard-nameLink").text.split()
        if len(name) == 1:
            name.append(None)
        location = self.driver.find_element(By.CSS_SELECTOR,"div.ProfileHeaderCard-location").text
        website = self.driver.find_element(By.CSS_SELECTOR,"div.ProfileHeaderCard-url").text
        bio = self.driver.find_element(By.CSS_SELECTOR,"p.ProfileHeaderCard-bio").text
        user = {}
        user['handle'] = twitterhandle
        user['firstname'] = name[0]
        user['lastname'] = name[1]
        user['location'] = location
        user['website'] = website
        user['bio'] = None
        for key in user:
            if user[key] is not None:
                user[key] = user[key].encode('utf-8')
        print(user)
        database_commands.insertTwitterHandler(user)


    def collectTweets(self, twitterhandle):
        """ Collects all/latest tweets
            Saves tweets to the database.

            @param twitterhandle     {String} name of users twitter handle
        """
        if not self.signedIn:
            self.signin()

        if '@' in twitterhandle:
            twitterhandle = twitterhandle.split('@')[1]

        # Store User Handle
        handles = database_commands.getHandler(twitterhandle)
        if len(handles) < 1:
            self.saveTwitterHandle(twitterhandle)

        sleep(1)

        self.liveSearch('from:' + twitterhandle)

        boxInd = 0
        lastNumBoxes = 0
        self.tweetboxes = self._loadAllTweets(numTimes=1)
        numBoxes = len(self.tweetboxes)
        inserted = True
        while lastNumBoxes != numBoxes and inserted:
            while boxInd < len(self.tweetboxes) and inserted:
                tweetbox = self.tweetboxes[boxInd]
                try:
                    tweet = self._getTweetStats(tweetbox)
                    tweet['handle'] = twitterhandle
                    inserted = database_commands.insertTweet(tweet)
                except:
                    inserted = True
                boxInd += 1
            if inserted:
                self.tweetboxes = self._loadAllTweets(numTimes=5)
                lastNumBoxes = numBoxes
                numBoxes = len(self.tweetboxes)
                self.logger.info('Completed ' + str(boxInd) + ' tweets, loaded ' + str(numBoxes-lastNumBoxes) + ' more tweets for ' + twitterhandle)

        self.logger.info(
            'Inserted ' + str(boxInd - 1) + ' tweets for ' + twitterhandle)

    def collectAllTweets(self, twitterhandle):
        """ Collects all tweets
            Saves tweets to the database.
            Continues searching until it finds no *new* tweets for 6 consecutive months.

            @param twitterhandle     {String} name of users twitter handle
        """
        if not self.signedIn:
            self.signin()

        if '@' in twitterhandle:
            twitterhandle = twitterhandle.split('@')[1]

        # Store User Handle
        handles = database_commands.getHandler(twitterhandle)
        if len(handles) < 1:
            self.saveTwitterHandle(twitterhandle)

        sleep(1)
        numZeros = 0
        totalInserted = 0
        twitterDates = utils.allTwitterDates
        drySpan = 6
        if self.phantom:
            twitterDates = utils.allTwitterDatesByDay
            drySpan = 180

        for i in range(len(twitterDates)-2,-1,-1):
            try:
                cmd = 'from:' + twitterhandle + '  since:' + twitterDates[i] + ' until:' + twitterDates[i+1]
                self.logger.info('searching: "' + cmd + "'")
                self.liveSearch(cmd)
                boxInd = 0
                lastNumBoxes = 0
                self.tweetboxes = self._loadAllTweets(numTimes=5)
                numBoxes = len(self.tweetboxes)
                numInserted = 0
                while lastNumBoxes != numBoxes:
                    while boxInd < len(self.tweetboxes):
                        tweetbox = self.tweetboxes[boxInd]
                        inserted = False
                        try:
                            tweet = self._getTweetStats(tweetbox)
                            tweet['handle'] = twitterhandle
                            inserted = database_commands.insertTweet(tweet,insertDuplicates=False)
                            if inserted:
                                numInserted += 1
                        except:
                            pass
                        boxInd += 1
                    self.tweetboxes = self._loadAllTweets(numTimes=5)
                    lastNumBoxes = numBoxes
                    numBoxes = len(self.tweetboxes)
                    self.logger.info('Inserted ' + str(numInserted) + ' tweets, loaded ' + str(numBoxes-lastNumBoxes) + ' more tweets for ' + twitterhandle)
                if numInserted == 0:
                    numZeros += 1
                else:
                    numZeros = 0
                if numZeros > drySpan:
                    break
                totalInserted += numInserted
                self.logger.info('Inserted ' + str(totalInserted) + ' TOTAL tweets for ' + twitterhandle + '. Zeros in-a-row: ' + str(numZeros))
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error scrolling through tweets!')
                self.logger.error(e)


    def countAllTweets(self, subject):
        """ Collects all tweets
            Saves tweets to the database.
            Continues searching until it finds no *new* tweets for 6 consecutive months.

            @param twitterhandle     {String} name of users twitter handle
        """
        if not self.signedIn:
            self.signin()

        sleep(1)
        numZeros = 0
        totalInserted = 0
        twitterDates = utils.allTwitterDates
        drySpan = 300
        twitterDates = utils.allTwitterDatesByDay

        for i in range(len(twitterDates)-2,-1,-1):
            try:
                cmd = subject + '  since:' + twitterDates[i] + ' until:' + twitterDates[i+1]
                self.logger.info('searching: "' + cmd + "'")
                self.liveSearch(cmd)
                self.tweetboxes = self._loadAllTweets()
                numBoxes = len(self.tweetboxes)
                self.logger.info('Counted ' + str(numBoxes))
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error scrolling through tweets!')
                self.logger.error(e)

    def _getTweetStats(self, tweetbox):
        """ Gets Tweet information

            @param tweetbox     {WebElement} Selenium element of tweet
            @returns tweet      {Dict} contains tweet text, time, type, itemid, favorites, retweets
        """
        logger = logging.getLogger('_getTweetStats')
        tweet = {}
        fulltext = tweetbox.text
        tstart = time()
        for text in fulltext.split():
            if '@' in text and len(text) > 4:
                tweet['handle'] = text
                break
        logger.debug('Getting tweet text')
        tweet['text'] = self._getTweetText(tweetbox)
        logger.debug('Getting tweet time')
        tweet['time'] = self._getTweetTime(tweetbox)
        logger.debug('Getting tweet type')
        tweet['type'] = tweetbox.get_attribute("data-item-type")
        logger.debug('Getting tweet itemid')
        tweet['itemid'] = tweetbox.get_attribute("data-item-id")
        words = fulltext.split('\n')
        logger.debug('Full tweet text: ' + " ".join(words))

        try:
            tweet['favorites'] = utils.convertCondensedNum(
                words[words.index('Like') + 1])
        except:
            tweet['favorites'] = -1
        try:
            tweet['retweets'] = utils.convertCondensedNum(
                words[words.index('Retweet') + 1])
        except:
            tweet['retweets'] = -1

        logger.debug("Tweet stats: " + json.dumps(tweet))

        # Get rid of weird characters
        for key in tweet:
            if tweet[key] is not None:
                try:
                    tweet[key] = tweet[key].encode('utf-8').decode('utf-8')
                except:
                    pass

        return tweet

    def liveSearch(self, search_term):
        """ Search for tweets

            @param search_term     {String} search term
        """
        if not self.signedIn:
            self.signin()

        self.driver.get(
            "http://www.twitter.com/" + self.settings['twittername'])
        sleep(1)
        try:
            elem = self.driver.find_element_by_name("q")
            elem.clear()
            elem.send_keys(search_term + Keys.RETURN)
        except:
            try:
                elem = self.driver.find_element_by_name("q")
                elem.clear()
                elem.send_keys(search_term + Keys.RETURN)
            except:
                pass
        sleep(1)
        if not self.settings['topResults']:
            try:
                self.driver.find_element_by_css_selector(
                    '.AdaptiveFiltersBar-target.AdaptiveFiltersBar-target--more.u-textUserColor.js-dropdown-toggle').click()
            except:
                sleep(3)
                self.driver.find_element_by_css_selector(
                    '.AdaptiveFiltersBar-target.AdaptiveFiltersBar-target--more.u-textUserColor.js-dropdown-toggle').click()
            sleep(1)
            self.driver.find_element_by_css_selector(
                "a[href*='f=tweets']").click()
            sleep(1)

        self.logger.debug(self.driver.current_url)
        if 'search' not in self.driver.current_url and search_term.split()[0] not in self.driver.current_url:
            self.logger.error('Problem with searching')

    def processFeed(self):
        logger = logging.getLogger('lib.processFeed')
        for tweetbox in self.tweetboxes:
            self.tweetbox = tweetbox
            tweetbox_text = tweetbox.text.split()
            twitter_handles = []
            all_twitter_handles = []
            dontEngage = False

            # check if you need to avoid this person
            tstart = time()
            logger.debug('Getting tweet stats')
            self.tweetinfo = self._getTweetStats(tweetbox)
            tstart = time()
            logger.debug('Checking whether to process tweet')
            if self.tweetinfo['handle'] is not None and not database_commands.hasHandle(self.tweetinfo['handle'], self.twittername):

                for word in self.settings['avoid_words']:
                    if word in tweetbox_text:
                        dontEngage = True
                        logger.info("need to avoid " + word)
                        break

                if not dontEngage:
                    logger.debug('Processing tweet')
                    problem = self._processTweet(tweetbox)
                else:
                    logger.info('Already interacted with ' + self.tweetinfo[
                                     'handle'] + ' in ' + str(time() - tstart))

    def _processTweet(self, tweetbox):
        """ Process Tweet for stuff?????

            @param tweetbox     {WebElement} Selenium element of tweet
            @returns True/False {Boolean}
        """
        self.driver.execute_script(
            "window.scrollTo(0, %s);" % str(tweetbox.location['y'] + 100))
        self.logger.info('Adding ' + self.tweetinfo['handle'] + ' to db')
        database_commands.add(self.tweetinfo['handle'], self.twittername)
        self.logger.debug('Trying to Follow')
        if random.randint(1, 100) <= self.settings['followingProbability']:
            try:
                self.logger.info('Following ' + self.tweetinfo['handle'])
                self._clickFollow(tweetbox)
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error following!')
                self.logger.error(e)
        if random.randint(1, 100) <= self.settings['favoritingProbability']:
            try:
                self.logger.info('favoriting ' + self.tweetinfo['handle'])
                self._clickFavorite(tweetbox)
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error favoriting!')
                self.logger.error(e)
        if random.randint(1, 100) <= self.settings['retweetingProbability']:
            try:
                self.logger.info('retweeting ' + self.tweetinfo['handle'])
                self._clickRetweet(tweetbox)
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error retweeting!')
                self.logger.error(e)
        if random.randint(1, 100) <= self.settings['replyProbability']:
            try:
                self.logger.info('replying ' + self.tweetinfo['handle'])
                self._clickReply(tweetbox)
            except Exception as e:
                traceback.print_exc()
                traceback.print_stack()
                self.logger.error('Error replying!')
                self.logger.error(e)
        return False

    def _getTweetText(self, tweetbox):
        """ Gets tweet text

            @param tweetbox     {WebElement} Selenium element of tweet
            @returns tweet_text {String} tweet text
        """
        tweet = tweetbox.find_element(By.TAG_NAME, "div")
        tweet = tweet.find_element(By.CSS_SELECTOR, "div.content")
        tweet_text = tweet.find_element(
            By.CSS_SELECTOR, "p.tweet-text").text  # .decode("utf-8") #.encode('utf-8')
        tweet_text = str(tweet_text)
        tweet_text = tweet_text.replace('\n', '')
        return tweet_text

    def _getTweetTime(self, tweetbox):
        """ Gets tweet timestamp

            @param tweetbox     {WebElement} Selenium element of tweet
            @returns tweet_time {Integer} unix timestamp for tweet creation
        """
        tweet = tweetbox.find_element(By.TAG_NAME, "div")
        tweet = tweet.find_element(By.CSS_SELECTOR, "div.content")
        tweet_time = tweet.find_element(
            By.CSS_SELECTOR, "div.stream-item-header")
        tweet_time = tweet_time.find_element(By.CSS_SELECTOR, "small.time")
        tweet_time = tweet_time.find_element(By.TAG_NAME, "a")
        tweet_time = tweet_time.find_element(
            By.CSS_SELECTOR, "span._timestamp")
        tweet_time = tweet_time.get_attribute("data-time")
        tweet_time = int(tweet_time)
        return tweet_time


    def _getTweetHandle(self, tweetbox):
        """ Gets tweets user handle

            @param tweetbox     {WebElement} Selenium element of tweet
            @returns text       {String} users handler
        """
        #for text in unidecode(tweetbox.text).split():
        for text in tweetbox.text.split():
            if '@' in text and len(text) > 4:
                return text
        return None

    def _clickTweetBox(self, tweetbox):
        """ Clicks on tweet element

            @param tweetbox     {WebElement} Selenium element of tweet
        """
        self.logger.info('Clicking ' + tweetbox.text.split('\n')[0])
        clickSuccess = False
        try:
            li = tweetbox.find_element(By.CSS_SELECTOR, "div")
            li.click()
            clickSuccess = True
        except:
            pass
        if not clickSuccess:
            try:
                self.logger.warn('Clicking using method 2')
                li = tweetbox.find_element(
                    By.CSS_SELECTOR, ".tweet.original-tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.js-original-tweet.with-user-actions")
                li.click()
                clickSuccess = True
            except:
                pass
        if not clickSuccess:
            try:
                self.logger.warn('Clicking using method 3')
                li = tweetbox.find_element(
                    By.CSS_SELECTOR, ".tweet.original-tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.js-original-tweet.favorited.with-non-tweet-action-follow-button")
                li.click()
                clickSuccess = True
            except:
                pass
        if not clickSuccess:
            try:
                self.logger.warn('Clicking using method 4')
                li = tweetbox.find_element(
                    By.CSS_SELECTOR, ".tweet.original-tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.js-original-tweet.with-non-tweet-action-follow-button")
                li.click()
                clickSuccess = True
            except:
                pass

    def _clickFavorite(self, tweetbox):
        """ Favorites a tweet

            @param tweetbox     {WebElement} Selenium element of tweet
        """
        css = '.' + \
            'ProfileTweet-actionButton ProfileTweet-follow-button js-tooltip'.replace(
                ' ', ',')
        buttons = tweetbox.find_elements(By.CSS_SELECTOR, css)
        button_num = 0
        for button in buttons:
            if ("Like" == button.text.split('\n')[0]):
                button.click()
                sleep(0.1)
                self.logger.debug('Favorited ' + self.tweetinfo['handle'])

    def _clickRetweet(self, tweetbox):
        """ Retweets a tweet

            @param tweetbox     {WebElement} Selenium element of tweet
        """
        css = '.' + \
            'ProfileTweet-actionButton ProfileTweet-follow-button js-tooltip'.replace(
                ' ', ',')
        buttons = tweetbox.find_elements(By.CSS_SELECTOR, css)
        button_num = 0
        for button in buttons:
            if ("Retweet" == button.text.split('\n')[0]):
                button.click()
                sleep(0.5)
                css = 't1-form tweet-form RetweetDialog-tweetForm isWithoutComment condensed'
                css = '.' + css.replace(' ', '.')
                retweet_box = self.driver.find_element(By.CSS_SELECTOR, css)
                css = '.btn.primary-btn.retweet-action'
                sleep(0.5)
                retweet_box.find_element(By.CSS_SELECTOR, css).click()
                self.logger.debug('Retweeted ' + self.tweetinfo['handle'])
                self.tweetinfo['type'] = 'rt'
                database_commands.insertTweet(self.tweetinfo)
                sleep(0.5)
                try:
                    css = 't1-form tweet-form RetweetDialog-tweetForm isWithoutComment condensed'
                    css = 'Icon Icon--close Icon--medium dismissIcon Icon--close Icon--medium dismiss'
                    css = 'modal-btn modal-close js-close'
                    css = '.' + css.replace(' ', '.')
                    exit = self.driver.find_element(By.CSS_SELECTOR, css)
                    exit.click()
                    return True
                    self.logger.debug('*' * 30)
                    self.logger.debug('Exited the Retweet')
                    self.logger.debug('*' * 30)
                except:
                    return True

    def _clickReply(self, tweetbox):
        """ Replies to a tweet

            @param tweetbox     {WebElement} Selenium element of tweet
        """
        reply_button = tweetbox.find_element_by_css_selector(
            '.' + 'ProfileTweet-actionButton u-textUserColorHover js-actionButton js-actionReply'.replace(' ', '.'))
        self.logger.info('Clicking reply')
        reply_button.click()

        sleep(0.5)
        textbox = tweetbox.find_element(
            By.CSS_SELECTOR, ".tweet-box.rich-editor.notie")
        thereply = random.choice(self.settings['replies'])
        self.logger.info('sending keys to ' + textbox.text)
        textbox.send_keys(thereply)
        twitter_button = tweetbox.find_element(
            By.CSS_SELECTOR, ".btn.primary-btn.tweet-action.tweet-btn.js-tweet-btn")
        self.logger.info('clicking twitter_button ' + twitter_button.text)
        twitter_button.click()
        sleep(0.5)
        responses = self.driver.find_elements(By.CSS_SELECTOR, ".message-text")
        for response in responses:
            self.logger.debug('Response to reply: ' + response.text)
        self.logger.info('Replied to ' + self.tweetinfo['handle'])
        sleep(0.3)

    def _clickFollow(self, tweetbox):
        """ Click the follow button

            First hover over user name
            Then float cursor over to the follow button
            Then press it

            @param tweetbox     {WebElement} Selenium element of tweet
        """
        # First get into view
        self.driver.execute_script(
            "window.scrollTo(0, %s);" % str(tweetbox.location['y'] - 100))

        css = '.' + \
            'fullname js-action-profile-name show-popup-with-id'.replace(
                ' ', ',')
        profile_text = tweetbox.find_elements(By.CSS_SELECTOR, css)[0]
        Hover = ActionChains(self.driver).move_to_element(profile_text)
        Hover.perform()
        sleep(1)
        try:
            css = '.' + \
                'profile-card ProfileCard with-banner component profile-header hovercard gravity-south weight-left'.replace(
                    ' ', ',')
            container = self.driver.find_elements(By.CSS_SELECTOR, css)[0]
        except:
            pass

        try:
            css = '.' + \
                'profile-card ProfileCard with-banner component profile-header hovercard gravity-north weight-left'.replace(
                    ' ', ',')
            container = self.driver.find_elements(By.CSS_SELECTOR, css)[0]
        except:
            pass

        try:
            sleep(0.5)
            # if (' not-following' in
            # unidecode(container.get_attribute("innerHTML"))):
            if (' not-following' in container.get_attribute("innerHTML")):
                sleep(0.5)
                css = '.' + \
                    'user-actions-follow-button js-follow-btn follow-button btn small small-follow-btn'.replace(
                        ' ', ',')
                follow_button = container.find_elements(
                    By.CSS_SELECTOR, css)[0]
                follow_button.click()
                sleep(0.5)

            Hover = ActionChains(self.driver).move_to_element_with_offset(
                profile_text, 10, 10)
            Hover.perform()
            self.logger.debug('Followed ' + self.tweetinfo['handle'])
        except:
            pass

    def followback(self):
        """Follow anyone that is following you"""

        if not self.signedIn:
            self.signin()

        self.driver.get(
            "http://www.twitter.com/" + self.settings['twittername'] + '/following')

        for i in range(3):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            sleep(.05)

        css = "user-actions btn-group not-muting can-dm not-following"
        css = '.' + css.replace(' ', '.')
        followers = self.driver.find_elements(By.CSS_SELECTOR, css)
        for follower in followers:
            if "Following" not in follower.text:
                css = '.' + \
                    'user-actions-follow-button js-follow-btn follow-button btn small small-follow-btn'.replace(
                        ' ', '.')
                buttons = follower.find_elements(By.CSS_SELECTOR, css)
                for button in buttons:
                    button.click()
                    sleep(.5)

    def getFollowers(self,twitterhandle):
        """Follow anyone that is following you"""

        if not self.signedIn:
            self.signin()

        self.driver.get(
            "http://www.twitter.com/" + twitterhandle + '/followers')

        for i in range(1000):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            sleep(.05)

        css = "u-linkComplex-target"
        css = '.' + css.replace(' ', '.')
        followers = self.driver.find_elements(By.CSS_SELECTOR, css)
        print(len(followers))
        #for follower in followers:
        #    print(follower.text)

    def _typeLikeHuman(self, element, text, enter=False):
        """ Types slowly like a human would

            @param element      {WebElement} element to 'type' charaters
            @param enter        {Boolean} send characters
        """
        for letter in text:
            element.send_keys(letter)
            sleep(float(random.randint(1, 100)) / 500.0)
        if enter:
            element.send_keys(Keys.RETURN)

    def tweet(self, text):
        """Sends a tweet

            @param text         {String} tweet text
        self.driver.get("http://www.twitter.com/")
        """
        self.driver.get("http://www.twitter.com/")
        try:
            twitterbox_inside = self.driver.find_element_by_css_selector(
                '.photo-tagging-container.user-select-container.hidden')
            twitterbox = self.driver.find_element_by_css_selector(
                '.' + 'tweet-box rich-editor notie'.replace(' ', '.'))
            twitterbox.click()
        except:
            pass
        try:
            twitterbox_inside = self.driver.find_element_by_css_selector(
                '.photo-tagging-container.user-select-container.hidden')
            twitterbox = self.driver.find_element_by_css_selector(
                '.' + 'tweet-box rich-editor notie is-showPlaceholder'.replace(' ', '.'))
            twitterbox.click()
        except:
            pass
        sleep(1)
        self._typeLikeHuman(twitterbox, text)
        self.driver.find_element_by_css_selector(
            '.' + 'btn primary-btn tweet-action tweet-btn js-tweet-btn'.replace(' ', '.')).click()


    def generateTweet(self):
        """ Generates tweet based on on the tweet corpus
        """
        if not self.signedIn:
            self.signin()
        self.tweet(utils.randomTweet())

    def generateTweet2(self,subreddit=None):
        """ Generates tweet based on something in a Reddit subreddit

            @param subreddit    {???} if not used, the config settings will be used
        """
        if not self.signedIn:
            self.signin()
        expressions = ['cool', 'Awesome!', 'Check it out!',
                       'My favorite!', 'The BEST', 'So awesome', 'I love this']
        r = praw.Reddit(user_agent='twitter-' + self.settings['twittername'])
        if subreddit is None:
            subreddit = self.settings['subreddit']
        submissions = r.get_subreddit(
            subreddit).get_hot(limit=50)
        for submission in submissions:
            print(submission.title)
            if title and len(submission.title) > 10 and len(submission.title) < 100:
                self.tweet(submission.title)
                break
            if not title and submission.media is not None and submission.ups > 0:
                self.tweet(random.choice(expressions) + ' ' + submission.url)
                break

    def logout(self):
        """Logs out and closes driver"""
        try:
            self.driver.get("http://www.twitter.com/")
            css = 'btn js-tooltip settings dropdown-toggle js-dropdown-toggle'
            logout_button = self.driver.find_elements(
                By.CSS_SELECTOR, '.' + css.replace(' ', '.'))
            logout_button[0].click()
            sleep(0.1)
            css = 'dropdown-link'
            dropdown_menu = self.driver.find_elements(
                By.CSS_SELECTOR, '.' + css.replace(' ', '.'))

            for menu in dropdown_menu:
                if 'Log out' in menu.text:
                    menu.click()
                    break

            if 'logged_out' in self.driver.current_url:
                self.logger.debug(
                    'Logged out from ' + self.settings['twittername'])
            else:
                self.logger.warn('Something went wrong with logging out')
        except:
            pass

        self.driver.close()
        self.signedIn = False

    def _getStats(self):
        """Gets stats from main page"""

        self.driver.get("http://www.twitter.com/")
        css = 'ProfileCardStats-statValue'
        following = self.driver.find_elements(
            By.CSS_SELECTOR, '.' + css.replace(' ', '.'))
        if 'K' in following[0].text:
            self.settings['tweets'] = float(
                following[0].text.replace('K', '')) * 1000
        else:
            try:
                self.settings['tweets'] = int(following[0].text.replace(',', ''))
            except:
                self.settings['tweets'] = -1
        try:
            self.settings['following'] = int(following[1].text.replace(',', ''))
        except:
            self.settings['following'] = -1
        try:
            self.settings['followers'] = int(following[2].text.replace(',', ''))
        except:
            self.settings['followers'] = -1
        try:
            self.logger.debug('Tweets: %s, Following: %s, Followers %s' % (
                following[0].text, following[1].text, following[2].text))
        except:
            pass
        with open(self.settings['file'], 'w') as f:
            f.write(json.dumps(self.settings, indent=4))




def getConfigFiles():
    f = []
    for (dirpath, dirnames, filenames) in walk('./data'):
        for filename in filenames:
            if '.json' in filename:
                f.append('./data/' + filename)
    return f


'''
# Load bots
bots = []
for f in getConfigFiles():
    print f
    bots.append(TwitterBot(f))
bots[0].collectTweets('lessig')


python
from lib import *
bot = TwitterBot('stefans.json')


bot = TwitterBot('musicsuggestions.json',headless=True)
bot.collectAllTweets('potus')

from lib import *
python
bot = TwitterBot('stefans.json')
handlers = [
    "HillaryClinton",
    "BernieSanders",
    "MartinOMalley",
    "lessig",
    "JimWebbUSA",
    "LincolnChafee",
    "realDonaldTrump",
    "JebBush",
    "RealBenCarson",
    "ChrisChristie",
    "tedcruz",
    "CarlyFiorina",
    "gov_gilmore",
    "LindseyGrahamSC",
    "GovMikeHuckabee",
    "BobbyJindal",
    "JohnKasich",
    "GovernorPataki",
    "RandPaul",
    "GovernorPerry",
    "marcorubio",
    "RickSantorum",
    "ScottWalker"
]
for handler in handlers:
    try:
        bot.collectTweets(handler)
    except:
        pass



'''
