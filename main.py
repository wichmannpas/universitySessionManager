#!/usr/bin/python3
# Copyright 2015 Pascal Wichmann
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

import configHandler
import priorityHandler


def main():
    userInput = input('[c] Create new config [l] load config: ')
    if userInput[::1] == 'c':
        configHandler.configHandler().createConfig()
    else:
        fileName = input('Enter configuration file name: ')
        configuration = configHandler.configHandler().loadConfig(fileName)
        priorityHandler.priorityHandler(configuration)

if __name__ == '__main__':
    main()
