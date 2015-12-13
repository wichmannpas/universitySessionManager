#!/usr/bin/python3
# Copyright 2015 Pascal Wichmann
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

import sqlite3
import itertools
import json
import math
import configHandler


class priorityHandler():
    database = sqlite3.connect(':memory:')
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

        # generate all possible priority combinations
        self.generateAllPossiblePriorityCombinations()

        # print all priority combinations
        self.printAllPriotyCombinations()

        # close database connection
        self.database.close()

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
        self.cursor.execute('''CREATE TABLE priorityCombinations
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
        allCombinations = itertools.product(*sessionIds)

        # save combinations to database
        self.savePossibleSessionCombinationsToDb(allCombinations)

    def savePossibleSessionCombinationsToDb(self, combinations):
        for combination in combinations:
            combinationJson = json.dumps(combination)
            self.cursor.execute('''INSERT INTO combinations (combination)
                                VALUES(?)''', [combinationJson])

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

    def savePriorityForSession(self, sessionId, priority):
        self.cursor.execute('UPDATE sessions SET priority=? WHERE sessionId=?',
                            [priority, sessionId[0]])

    def printAllPriotyCombinations(self):
        self.cursor.execute('''SELECT combination FROM priorityCombinations
                            ORDER BY rating ASC''')
        combinations = self.cursor.fetchall()

        if len(combinations) > 1:
            print('There are multiple combinations with the same rating.')

        for combination in combinations:
            self.savePriorityCombinationsToSessions(json.loads(combination[0]))
            self.printPriorities()

    def savePriorityCombinationsToSessions(self, combination):
        # copies the priorities from a single priority combinations to the
        # sessions table
        for module in combination:
            priority = 1
            for session in module:
                self.savePriorityForSession(session, priority)
                priority += 1

    def printPriorities(self):
        print('')
        print('The following priorities have been calculated:')
        print('')

        moduleId = 0
        for module in self.modules:
            name = self.getModuleNameById(moduleId)['name']
            print(name)
            print('='*len(name))

            self.cursor.execute('''SELECT * FROM sessions WHERE module=?
                                ORDER BY priority''', [moduleId])
            priorities = self.cursor.fetchall()

            for priority in priorities:
                session = self.getSessionById(moduleId, priority[0])
                print(str(priority[7]) + ': ' +
                      configHandler.configHandler().printSingleSession(session))

            moduleId += 1

    def getModuleById(self, id):
        allModules = self.modules
        for module in allModules:
            currentId = list(module.keys())
            if currentId[0] == id:
                return list(module.values())

    def getModuleNameById(self, id):
        return self.getModuleById(id)[0]

    def generateAllPossiblePriorityCombinations(self):
        allCombinations = []
        for module in self.modules:
            moduleId = list(module.keys())[0]
            allCombinations.append(
                self.generatePriorityCombinationsForOneModule(moduleId))
        priorityCombinations = itertools.product(*allCombinations)

        self.ratePriorityCombinations(priorityCombinations)

    def ratePriorityCombinations(self, priorityCombinations):
        for priorityCombination in priorityCombinations:
            rating = 0
            combinations = itertools.product(
                *priorityCombination)

            i = 1
            for combination in combinations:
                likeliness = self.calculateLikeliness(len(self.modules), i)
                rating += likeliness * self.getCombinationRating(combination)
                i += 1

            self.savePriorityCombinationRating(priorityCombination, rating)

    def calculateLikeliness(self, moduleCount, iteration):
        # the sum of all binomial coefficients is 2^n. We do not consider nC0,
        # therefore we use 2^n - 1. In total, the possibilities per step can be
        # calculated by (2^n - 2) * (h - 1) + 1 where n is the number of
        # considered priorities and h the highest priority occuring (-2 because
        # we do not want to consider a combination only consisting of h multiple
        # times, therefore we reduce the number of possibilities per iteration
        # and add them to the total result)
        # that formula results in h = ((i - 1)/(2^2 - 2)) + 1 (where i is the
        # current iteration
        # the calculation is not absolute excatly, as it is possible to have
        # modules with less than maxPriority sessions; however it should be
        # accurate enough given the general limitations of this algorithm
        highestPriority = ((iteration - 1) / (math.pow(2, 2) - 2)) + 1

        # likeliness is 1 / h, i.e. 1 for the combination of all first
        # priorities, 1 / 2 when at least one priority 2 is used, 1/10 when one
        # priority 10 is used etc
        return 1 / highestPriority

    def savePriorityCombinationRating(self, combination, rating):
        # check if there is already a priority combination with better rating -
        # then we can truncate this combination immediately
        self.cursor.execute('SELECT * FROM priorityCombinations WHERE rating>?',
                            [rating])
        if len(self.cursor.fetchall()) == 0:
            self.cursor.execute('''INSERT INTO priorityCombinations
                                (combination, rating)
                                VALUES (?, ?)''', [json.dumps(combination),
                                                   rating])
            # delete all combinations with worse rating
            self.cursor.execute('''DELETE FROM priorityCombinations
                                WHERE rating<?''', [rating])

    def getCombinationRating(self, combination):
        self.cursor.execute(
            'SELECT rating FROM combinations WHERE combination=?',
            [json.dumps(combination)])
        return self.cursor.fetchone()[0]

    def generatePriorityCombinationsForOneModule(self, moduleId):
        sessions = self.getSessionIdsOfModule(moduleId)
        priorities = self.settings['priorities']
        if priorities > len(sessions):
            priorities = len(sessions)

        return itertools.permutations(sessions, r=priorities)

    def getSessionIdsOfModule(self, moduleId):
        self.cursor.execute('SELECT sessionId FROM sessions WHERE module=?',
                            [moduleId])
        sessions = self.cursor.fetchall()

        # make tuple to list
        sessionsList = []
        for session in sessions:
            sessionsList.append(session[0])
        return sessions
