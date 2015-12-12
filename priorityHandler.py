import sqlite3
import itertools
import json
import configHandler


class priorityHandler():
    database = sqlite3.connect('tmp.db')  # ':memory:')
    cursor = database.cursor()
    modules = []
    settings = {}

    def __init__(self, configuration):
        self.populateDb()

        self.settings = configuration['settings']

        # fill tables with modules from configuration
        self.populateTables(configuration['modules'])

        self.generateAllPossibleSessionCombinations()

        # iterate through all possible combinations and generate ratings
        self.rateSessionCombinations()

    def populateDb(self):
        self.cursor.execute('''CREATE TABLE modules
                       (moduleId INTEGER PRIMARY KEY,
                        moduleName TEXT)''')
        self.cursor.execute('''CREATE TABLE sessions
                       (sessionId INTEGER PRIMARY KEY,
                        module INTEGER,
                        weekday INTEGER,
                        hour INTEGER,
                        minute INTEGER,
                        duration INTEGER,
                        userPriority INTEGER,
                        priority INTEGER)''')
        self.cursor.execute('''CREATE TABLE combinations
                       (id INTEGER PRIMARY KEY,
                       combination TEXT,
                       rating INTEGER)''')
        self.cursor.execute('''CREATE TABLE schedule
                       (id INTEGER PRIMARY KEY,
                       weekday INTEGER,
                       hourStart INTEGER,
                       hourEnd INTEGER,
                       minuteStart INTEGER,
                       minuteEnd INTEGER,
                       userPriority INTEGER)''')
        self.database.commit()

    def populateTables(self, configuration):
        i = 0
        for module in configuration:
            # save module
            self.cursor.execute('''INSERT INTO modules (moduleId, moduleName)
                                VALUES(?, ?)''', [i, module['name']])

            moduleWithIds = {'name': module['name'], 'sessions': []}
            # sessions of module
            for session in module['sessions']:
                # save session
                self.cursor.execute('''INSERT INTO sessions (module, weekday,
                                    hour, minute, duration, userPriority,
                                    priority)
                                    VALUES(?, ?, ?, ?, ?, ?, ?)''',
                                    [i, session['weekday'], session['hour'],
                                     session['minute'], session['duration'],
                                     session['userPriority'], -1])
                sessionDbId = self.cursor.lastrowid
                moduleWithIds['sessions'].append({sessionDbId: session})

            # add module to modules array (in order to get the same id as in the
            # db)
            self.modules.append({i: moduleWithIds})

            i += 1

        self.database.commit()

    def generateAllPossibleSessionCombinations(self):
        # generate list only containing session ids for each module
        sessionIds = []
        for module in self.modules:
            moduleContent = list(module.values())
            thisSessions = []
            thisSessionIds = moduleContent[0]['sessions']
            for sessionId in thisSessionIds:
                thisSessions.append(list(sessionId.keys()))
            sessionIds.append(thisSessions)
        allCombinations = list(itertools.product(*sessionIds))

        # save combinations to database
        self.savePossibleSessionCombinationsToDb(allCombinations)

    def savePossibleSessionCombinationsToDb(self, combinations):
        for combination in combinations:
            combinationJson = json.dumps(combination)
            self.cursor.execute('''INSERT INTO combinations (combination,
                                rating)
                                VALUES(?, ?)''', [combinationJson, 0])
            self.database.commit()

    def rateSessionCombinations(self):
        self.cursor.execute('SELECT * FROM combinations')
        combinations = self.cursor.fetchall()
        for combination in combinations:
            # generate schedule for this combination
            self.generateSchedule(json.loads(combination[1]))

            # save rating
            rating = self.rateSchedule()

            self.emptySchedule()

            self.cursor.execute('UPDATE combinations SET rating=? WHERE id=?',
                                [rating, combination[0]])
            self.database.commit()

    def generateSchedule(self, combination):
        i = 0
        for session in combination:
            sessionData = self.getSessionById(i, session[0])
            weekday = sessionData['weekday']
            hourStart = sessionData['hour']
            minuteStart = sessionData['minute']
            end = configHandler.configHandler().getEndTime(
                {'hour': hourStart, 'minute': minuteStart,
                 'duration': sessionData['duration']})
            hourEnd = end['hour']
            minuteEnd = end['minute']
            userPriority = sessionData['userPriority']

            # add session to temporary schedule
            self.cursor.execute('''INSERT INTO schedule (weekday, hourStart,
                                hourEnd, minuteStart, minuteEnd, userPriority)
                                VALUES(?, ?, ?, ?, ?, ?)''',
                                [weekday, hourStart, hourEnd, minuteStart,
                                 minuteEnd, userPriority])
            self.database.commit()

            i += 1

    def rateSchedule(self):
        self.cursor.execute('SELECT * FROM schedule')
        schedule = self.cursor.fetchall()

        rating = 0  # value will be reduced when collissions are detected

        # check each schedule entry for collisions with other events
        for entry in schedule:
            # calculate start time in minutes since midnight
            startTime = 60 * int(entry[2]) + int(entry[4])
            endTime = 60 * int(entry[3]) + int(entry[5])

            # add user rating of session
            rating += int(entry[6] / 10)

            # compare item to all other items on same weekday and calculate
            # rating
            for toCompare in schedule:
                if entry[0] == toCompare[0] or entry[1] != toCompare[1]:
                    # do not compare entry with itself and only with sessions on
                    # same weekday
                    continue
                startTimeCompare = 60 * int(toCompare[2]) + int(toCompare[4])
                endTimeCompare = 60 * int(toCompare[3]) + int(toCompare[5])

                # check for overlapping
                rating -= self.calculateSessionSingleRating(
                    [startTime, endTime], [startTimeCompare, endTimeCompare])

        return rating

    def calculateSessionSingleRating(self, time, timeCompare):
        minDifference = self.settings['minDifference']
        # merge minDifference into times of first event (not to second in order
        # to not have higher impact (otherwise would count multiple times)
        time[0] -= minDifference
        time[1] += minDifference

        singleRating = 0

        # first case: first entry overlaps second on both sides
        if time[0] < timeCompare[0] and time[1] > timeCompare[1]:
            # return left and right overhead
            singleRating = (abs(abs((timeCompare[1] - time[0])) +
                            abs((time[1] - timeCompare[0]))))
        # second case: second entry overlaps first entry on both sides
        elif timeCompare[0] < time[0] and timeCompare[1] > time[1]:
            # return left and right overhead
            singleRating = (abs(abs((timeCompare[1] - time[0])) +
                            abs((time[1] - timeCompare[0]))))
        # third case: first entry overlaps second only on the right side
        elif timeCompare[0] < time[1] and timeCompare[1] > time[0]:
            # return right overhead of second entry
            singleRating = abs(timeCompare[1] - time[0])
        # fourth case: first entry overlaps second only on the left side
        elif timeCompare[0] < time[1] and timeCompare[1] > time[0]:
            # return left overhead of second entry
            singleRating = abs(time[1] - timeCompare[0])

        if singleRating > minDifference:
            # let real collisions have more impact than collisions which only
            # affect the time frame between events (events overlapping on both
            # sides will have more impact if they are exceeding the limit on
            # total (i.e. on both sides for minDifference / 2 or on one side
            # completely and on the other side not)
            singleRating = singleRating * 2

        return singleRating

    def getSessionById(self, moduleId, sessionId):
        sessions = list(self.modules[moduleId].values())[0]['sessions']
        # iterate through all sessions to find searched session
        for session in sessions:
            currentId = list(session.keys())[0]
            if currentId == sessionId:
                return list(session.values())[0]

    def emptySchedule(self):
        self.cursor.execute('DELETE FROM schedule')
        self.database.commit()
