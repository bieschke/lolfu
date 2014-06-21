#!/usr/bin/env python

import anydb

class ChampionDatabase:

	def __enter__(self):
		self.db = anydb.open('champion', 'c')
		return self.db

	def __exit__(self, type, value, traceback):
		self.db.close()

	def _get_int(self, key):
		return int(self.db.get(key, 0))

	def _increment(self, key):
		val = int(self.db.get(key, 0))
		self.db[key] = str(val + 1)
		return self.db[key]

	def loss_key(self, champion_id):
		return 'loss_%d' % champion_id

	def loss_vs_key(self, loser_id, victor_id):
		return 'loss_%d_vs_%d' % (loser_id, victor_id)

	def win_key(self, champion_id):
		return 'win_%d' % champion_id

	def win_vs_key(self, victor_id, loser_id):
		return 'win_%d_vs_%d' % (victor_id, loser_id)

	def losses_by_champion(self, champion_id):
		return self._get_int(self.loss_key(champion_id))

	def losses_by_champion_vs_champion(self, champion_id, vs_id):
		return self._get_int(self.loss_vs_key(champion_id, vs_id))

	def wins_by_champion(self, champion_id):
		return self._get_int(self.win_key(champion_id))

	def wins_by_champion_vs_champion(self, champion_id, vs_id):
		return self._get_int(self.win_vs_key(champion_id, vs_id))

	def win_loss(self, victor_id, loser_id):
		self._increment(self.loss_key(loser_id))
		self._increment(self.loss_vs_key(loser_id, victor_id))
		self._increment(self.win_key(victor_id))
		self._increment(self.win_vs_key(victor_id, loser_id))
