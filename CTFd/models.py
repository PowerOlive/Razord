#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
from flask.ext.sqlalchemy import SQLAlchemy
from CTFd.config import DEFAULT_SCORE

from socket import inet_aton, inet_ntoa
from struct import unpack, pack
from passlib.hash import bcrypt_sha256

import datetime
import hashlib
import json


def sha512(string):
    return hashlib.sha512(string).hexdigest()


def ip2long(ip):
    return unpack('!I', inet_aton(ip))[0]


def long2ip(ip_int):
    return inet_ntoa(pack('!I', ip_int))

db = SQLAlchemy()


class Pages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route = db.Column(db.String(80), unique=True)
    html = db.Column(db.Text)

    def __init__(self, route, html):
        self.route = route
        self.html = html

    def __repr__(self):
        return "<Tag {0} for challenge {1}>".format(self.tag, self.chal)


class Challenges(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    description = db.Column(db.Text)
    value = db.Column(db.Integer)
    category = db.Column(db.String(80))
    flags = db.Column(db.Text)
    hidden = db.Column(db.Boolean)

    def __init__(self, name, description, value, category, flags, hidden=False):
        self.name = name
        self.description = description
        self.value = value
        self.category = category
        self.flags = json.dumps(flags)
        self.hidden = hidden

    def __repr__(self):
        return '<chal %r>' % self.name


class Tags(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chal = db.Column(db.Integer, db.ForeignKey('challenges.id'))
    tag = db.Column(db.String(80))

    def __init__(self, chal, tag):
        self.chal = chal
        self.tag = tag

    def __repr__(self):
        return "<Tag {0} for challenge {1}>".format(self.tag, self.chal)


class Files(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chal = db.Column(db.Integer, db.ForeignKey('challenges.id'))
    location = db.Column(db.Text)

    def __init__(self, chal, location):
        self.chal = chal
        self.location = location

    def __repr__(self):
        return "<File {0} for challenge {1}>".format(self.location, self.chal)


class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, index=True)
    email = db.Column(db.String(128), unique=True, index=True)
    password = db.Column(db.String(128))
    website = db.Column(db.String(128))
    affiliation = db.Column(db.String(128))
    country = db.Column(db.String(32))
    bracket = db.Column(db.String(32))
    banned = db.Column(db.Boolean, default=False)
    admin = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=DEFAULT_SCORE)

    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = bcrypt_sha256.encrypt(str(password))

    def __repr__(self):
        return '<team %r>' % self.name

    def score(self):
        score = db.func.sum(Challenges.value).label('score')
        team = db.session.query(Solves.teamid, score).join(Teams)\
            .join(Challenges).filter(Teams.banned == None, Teams.id==self.id)\
            .group_by(Solves.teamid).first()
        if team:
            return team.score
        else:
            return 0

    def place(self):
        score = db.func.sum(Challenges.value).label('score')
        quickest = db.func.max(Solves.date).label('quickest')
        teams = db.session.query(Solves.teamid).join(Teams).join(Challenges)\
            .filter(Teams.banned == None).group_by(Solves.teamid)\
            .order_by(score.desc(), quickest).all()
        #http://codegolf.stackexchange.com/a/4712
        try:
            i = teams.index((self.id,)) + 1
            k = i % 10
            return "%d%s" % (i, "tsnrhtdd"[(i / 10 % 10 != 1) * (k < 4) * k::4])
        except ValueError:
            return 0


class Gameboxs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'), index=True)
    teamid = db.Column(db.Integer, db.ForeignKey('teams.id'), index=True)
    ip = db.Column(db.Integer)

    def __init__(self, chalid, teamid, ip):
        self.ip = ip2long(ip)
        self.chalid = chalid
        self.teamid = teamid


class Rounds(db.Model):
    round = db.Column(db.Integer, primary_key=True)
    begin_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)


# 原版里没有用到这个结构
class Keys(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'))
    key_type = db.Column(db.Integer)
    flag = db.Column(db.Text, index=True)
    gameboxid = db.Column(db.Integer, db.ForeignKey('gameboxs.id'), index=True)
    round = db.Column(db.Integer, db.ForeignKey('rounds.round'), index=True)
    gamebox = db.relationship('Gameboxs', foreign_keys="Keys.gameboxid", lazy='joined')

    def __init__(self, chal, flag, key_type, gamebox, round):
        self.chalid = chal
        self.flag = flag
        self.key_type = key_type
        self.gameboxid = gamebox
        self.round = round

    def __repr__(self):
        return self.flag


class Solves(db.Model):
    # __table_args__ = (db.UniqueConstraint('chalid', 'teamid'), {})
    id = db.Column(db.Integer, primary_key=True)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'), index=True)
    teamid = db.Column(db.Integer, db.ForeignKey('teams.id'), index=True)
    # vic_teamid = db.Column(db.Integer, db.ForeignKey('teams.id'), index=True)
    keyid = db.Column(db.Integer, db.ForeignKey('keys.id'), index=True)
    round = db.Column(db.Integer, db.ForeignKey('rounds.round'), index=True)
    ip = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    team = db.relationship('Teams', foreign_keys="Solves.teamid", lazy='joined')
    chal = db.relationship('Challenges', foreign_keys="Solves.chalid", lazy='joined')
    key = db.relationship('Keys', foreign_keys="Solves.keyid", lazy='joined')
    # value = db.Column(db.Integer)

    def __init__(self, keyid, teamid, chalid, round, ip):
        self.ip = ip2long(ip)
        self.keyid = keyid
        self.teamid = teamid
        self.round = round
        self.chalid = chalid
        # self.value = value

    def __repr__(self):
        return '<solves %r>' % self.chal


class Checks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # status 0:OK , >0:SOMETHING WRONG
    status = db.Column(db.Integer)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'), index=True)
    round = db.Column(db.Integer, db.ForeignKey('rounds.round'), index=True)
    teamid = db.Column(db.Integer, db.ForeignKey('teams.id'), index=True)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, teamid, chalid, roundid):
        self.ip = ip2long(ip)
        self.teamid = teamid
        self.roundid = roundid
        self.chalid = chalid


# 不存储错误提交,弃用此结构
class WrongKeys(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'))
    team = db.Column(db.Integer, db.ForeignKey('teams.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    flag = db.Column(db.Text)
    chal = db.relationship('Challenges', foreign_keys="WrongKeys.chalid", lazy='joined')

    def __init__(self, team, chalid, flag):
        self.team = team
        self.chalid = chalid
        self.flag = flag

    def __repr__(self):
        return '<wrong %r>' % self.flag


class Tracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.BigInteger)
    team = db.Column(db.Integer, db.ForeignKey('teams.id'))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, ip, team):
        self.ip = ip2long(ip)
        self.team = team

    def __repr__(self):
        return '<ip %r>' % self.team


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.Text)
    value = db.Column(db.Text)

    def __init__(self, key, value):
        self.key = key
        self.value = value
