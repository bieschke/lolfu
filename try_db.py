#!/usr/bin/env python

import champ_db

with champ_db.ChampionDatabase() as db:
    db.win_loss(12, 34)
