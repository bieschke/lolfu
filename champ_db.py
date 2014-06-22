#!/usr/bin/env python

import json


class ChampionDatabase:
    db_filename = 'champion.db'
    win_key = 'win'
    loss_key = 'loss'

    def __init__(self):
        self.data = {self.win_key: {}, self.loss_key: {}}

    def __enter__(self):
        try:
            with open(self.db_filename, 'r') as f:
                self.data = json.load(f)
        except IOError:
            pass  # first time file is created, we'll do that later
        return self

    def __exit__(self, type, value, traceback):
        with open(self.db_filename, 'w') as f:
            json.dump(self.data, f)

    def win_loss(self, victor_id, loser_id):
        victor_id = str(victor_id)
        loser_id = str(loser_id)
        self.data[self.win_key].setdefault(victor_id, {loser_id: 0})
        self.data[self.win_key][victor_id][loser_id] += 1
        self.data[self.loss_key].setdefault(loser_id, {victor_id: 0})
        self.data[self.loss_key][loser_id][victor_id] += 1
