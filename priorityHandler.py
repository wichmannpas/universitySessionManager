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

        self.generateAllPossibleCombinations()

        # iterate through all possible combinations and generate ratings
        self.rateCombinations()

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
                            minuteEnd INTEGER)''')
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
                                    hour, minute, duration, priority)
                                    VALUES(?, ?, ?, ?, ?, ?)''',
                                    [i, session['weekday'], session['hour'],
                                     session['minute'], session['duration'],
                                     -1])
                sessionDbId = self.cursor.lastrowid
                moduleWithIds['sessions'].append({sessionDbId: session})

            # add module to modules array (in order to get the same id as in the
            # db)
            self.modules.append({i: moduleWithIds})

            i += 1

        self.database.commit()

    def generateAllPossibleCombinations(self):
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
        self.savePossibleCombinationsToDb(allCombinations)

    def savePossibleCombinationsToDb(self, combinations):
        for combination in combinations:
            combinationJson = json.dumps(combination)
            self.cursor.execute('''INSERT INTO combinations (combination,
                                rating)
                                VALUES(?, ?)''', [combinationJson, 0])
            self.database.commit()

    def rateCombinations(self):
        self.cursor.execute('SELECT * FROM combinations')
        combinations = self.cursor.fetchall()
        for combination in combinations:
            # generate schedule for this combination
            self.generateSchedule(json.loads(combination[1]))

            # save rating
            rating = self.rateSchedule()
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

            # add session to temporary schedule
            self.cursor.execute('''INSERT INTO schedule (weekday, hourStart,
                                hourEnd, minuteStart, minuteEnd)
                                VALUES(?, ?, ?, ?, ?)''', [weekday, hourStart,
                                                           hourEnd, minuteStart,
                                                           minuteEnd])
            self.database.commit()

            i += 1

    def rateSchedule(self):
        pass

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
