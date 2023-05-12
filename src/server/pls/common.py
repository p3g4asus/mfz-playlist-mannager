import asyncio
from asyncio import Event
from collections import OrderedDict
from functools import partial
import json
import logging
from os import remove, rename
import socket
import subprocess
import sys
import traceback
import zlib
from base64 import b64encode
from os.path import exists, join, isfile, splitext, split

from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import SimpleUDPClient

from common.const import (CMD_ADD, CMD_CLOSE, CMD_DOWNLOAD, CMD_DEL, CMD_DUMP, CMD_IORDER,
                          CMD_MOVE, CMD_PLAYID, CMD_PLAYITSETT, CMD_PLAYSETT,
                          CMD_REN, CMD_SEEN, CMD_SORT, MSG_BACKEND_ERROR,
                          MSG_INVALID_PARAM, MSG_NAME_TAKEN,
                          MSG_PLAYLIST_NOT_FOUND, MSG_PLAYLISTITEM_NOT_FOUND, MSG_TASK_ABORT,
                          MSG_UNAUTHORIZED)
from common.playlist import (LOAD_ITEMS_ALL, LOAD_ITEMS_NO, LOAD_ITEMS_UNSEEN,
                             Playlist, PlaylistItem)
from common.utils import AbstractMessageProcessor, MyEncoder

_LOGGER = logging.getLogger(__name__)

DUMP_LIMIT = 50


class MessageProcessor(AbstractMessageProcessor):
    def __init__(self, db, dldir='', **kwargs):
        super().__init__(db, **kwargs)
        self.dl_dir = dldir
        self.dl_q = OrderedDict()
        self.osc_s = None
        self.osc_t = None
        self.osc_c = None

    def interested(self, msg):
        return msg.c(CMD_DEL) or msg.c(CMD_REN) or msg.c(CMD_DUMP) or\
            msg.c(CMD_ADD) or msg.c(CMD_SEEN) or msg.c(CMD_MOVE) or\
            msg.c(CMD_IORDER) or msg.c(CMD_SORT) or msg.c(CMD_PLAYID) or\
            msg.c(CMD_PLAYSETT) or msg.c(CMD_PLAYITSETT) or msg.c(CMD_DOWNLOAD)

    async def processMove(self, msg, userid, executor):
        pdst = msg.playlistId()
        itx = msg.playlistItemId()
        if pdst and itx:
            pdst = await Playlist.loadbyid(self.db, rowid=pdst)
            if not pdst:
                return msg.err(10, MSG_PLAYLIST_NOT_FOUND, playlist=None)
            else:
                pdst = pdst[0]
            if pdst.useri != userid:
                return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
            it = await PlaylistItem.loadbyid(self.db, itx)
            if not it:
                return msg.err(14, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
            psrc = await Playlist.loadbyid(self.db, rowid=it.playlist, loaditems=LOAD_ITEMS_NO)
            if not psrc:
                return msg.err(16, MSG_PLAYLIST_NOT_FOUND, playlist=None)
            else:
                psrc = psrc[0]
            if psrc.useri != userid:
                return msg.err(502, MSG_UNAUTHORIZED, playlist=None)
            if not pdst.rowid:
                rv = await pdst.toDB(self.db)
                if not rv:
                    return msg.err(2, MSG_NAME_TAKEN, playlist=None)
            rv = await it.move_to(pdst.rowid, self.db)
            if rv:
                pdst.items.append(it)
                return msg.ok(playlist=pdst)
            else:
                return msg.err(4, MSG_BACKEND_ERROR, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processAdd(self, msg, userid, executor):
        x = msg.playlistObj()
        if x:
            if x.useri != userid:
                return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
            rv = await x.toDB(self.db)
            if rv:
                return msg.ok(playlist=x)
            else:
                return msg.err(2, MSG_NAME_TAKEN, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processDump(self, msg, userid, executor):
        u = msg.f("useri", (int,))
        if u:
            if u != userid:
                return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
            vidx = msg.f('fast_videoidx')
            if isinstance(vidx, int) and vidx < 0:
                zlibc = -vidx
                vidx = None
            else:
                zlibc = -1
            try:
                all = int(msg.f('load_all'))
            except Exception:
                all = 0
            pl = await Playlist.loadbyid(self.db, rowid=msg.playlistId(), name=msg.playlistName(), useri=u, offset=vidx, limit=DUMP_LIMIT, loaditems=LOAD_ITEMS_UNSEEN if not all else LOAD_ITEMS_ALL if all > 0 else LOAD_ITEMS_NO)
            _LOGGER.debug("Playlists are %s" % str(pl))
            if len(pl):
                if zlibc > 0:
                    pl = str(b64encode(zlib.compress(bytes(json.dumps(pl, cls=MyEncoder), 'utf-8'), zlibc)), 'utf-8')
                return msg.ok(playlist=None, playlists=pl, fast_videoidx=vidx, fast_videostep=DUMP_LIMIT if vidx is not None else None)
        return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processRen(self, msg, userid, executor):
        x = msg.playlistId()
        if x is not None:
            pls = await Playlist.loadbyid(self.db, rowid=x, loaditems=LOAD_ITEMS_NO)
            if pls:
                if pls[0].useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                pls[0].name = msg.f("to")
                rv = await pls[0].toDB(self.db)
                if rv:
                    return msg.ok(playlist=x, name=pls[0].name)
                else:
                    return msg.err(2, MSG_NAME_TAKEN, playlist=None)
            else:
                return msg.err(3, MSG_PLAYLIST_NOT_FOUND, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processSeen(self, msg, userid, executor):
        llx = msg.playlistItemId()
        if llx is not None:
            lx = llx if isinstance(llx, list) else [llx]
            seen = msg.f("seen")
            if isinstance(seen, list) and len(seen) != len(lx):
                return msg.err(20, MSG_INVALID_PARAM, playlistitem=None)
            elif not isinstance(seen, list):
                seen = [seen] * len(lx)
            nmod = 0
            for i, x in enumerate(lx):
                it = await PlaylistItem.loadbyid(self.db, rowid=x)
                if it:
                    pls = await Playlist.loadbyid(self.db, rowid=it.playlist, loaditems=LOAD_ITEMS_NO)
                    if pls:
                        if pls[0].useri != userid:
                            return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                        if not await it.setSeen(self.db, seen[i], commit=False):
                            return msg.err(2, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                        else:
                            nmod += 1
                            todb = False
                            if seen[i] and it.dl and exists(it.dl) and isfile(it.dl):
                                try:
                                    remove(it.dl)
                                    it.dl = None
                                    todb = True
                                except Exception:
                                    pass
                            if isinstance(it.conf, dict) and 'sec' in it.conf:
                                del it.conf['sec']
                                todb = True
                            if todb:
                                await it.toDB(self.db, commit=False)
                    else:
                        return msg.err(4, MSG_PLAYLIST_NOT_FOUND, playlistitem=None)
                else:
                    return msg.err(3, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
            if nmod:
                await self.db.commit()
        else:
            return msg.err(1, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
        return msg.ok(playlistitem=llx)

    async def processPlayItSett(self, msg, userid, executor):
        x = msg.playlistItemId()
        it = await PlaylistItem.loadbyid(self.db, rowid=x)
        if it:
            pls = await Playlist.loadbyid(self.db, rowid=it.playlist, loaditems=LOAD_ITEMS_NO)
            if pls:
                if pls[0].useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                it.conf = msg.conf
                if isinstance(it.conf, str):
                    it.conf = json.loads(it.conf)
                if not await it.toDB(self.db):
                    return msg.err(2, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
            else:
                return msg.err(4, MSG_PLAYLIST_NOT_FOUND, playlistitem=None)
        else:
            return msg.err(3, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
        return msg.ok(playlistitem=x)

    @staticmethod
    def find_free_port():
        sock = socket.socket()
        sock.bind(('', 0))
        return sock.getsockname()[1]

    def processDlSendJob(self, job, *_):
        self.osc_c.send_message('/startjob', (job[0], json.dumps(job[1])))

    def processDlJobProgress(self, _, status):
        self.status['dl'] = json.loads(status)

    def processDlJobDone(self, _, exits):
        self.status['dlx'] = json.loads(exits)
        self.osc_c.send_message('/destroy', 1)

    async def processDlInitOSCClientServer(self, job):
        dispatcher = Dispatcher()
        dispatcher.map("/iamalive", partial(self.processDlSendJob, job))
        dispatcher.map("/jobprogress", self.processDlJobProgress)
        dispatcher.map("/jobdone", self.processDlJobDone)
        myport = self.find_free_port()
        self.osc_s = AsyncIOOSCUDPServer(('127.0.0.1', myport), dispatcher, asyncio.get_event_loop())
        self.osc_t, _ = await self.osc_s.create_serve_endpoint()  # Create datagram endpoint and start serving
        hisport = self.find_free_port()
        self.osc_c = SimpleUDPClient('127.0.0.1', hisport)
        return (str(hisport), str(myport))

    def processDlOpenAndWait(self, args):
        pthfile = join(split(__file__)[0], '..', '..', 'youtubedl_process.py')
        subprocess.run([sys.executable, pthfile, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    async def processDl(self, msg, userid, executor):
        x = msg.playlistItemId()
        if x:
            it = await PlaylistItem.loadbyid(self.db, rowid=x)
            if it:
                pls = await Playlist.loadbyid(self.db, rowid=it.playlist, loaditems=LOAD_ITEMS_NO)
                if pls:
                    if pls[0].useri != userid:
                        return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                    elif self.osc_s:
                        k = str(x)
                        if k in self.dl_q:
                            tp = self.dl_q[k]
                            tp[0].set_from_dict(dict(rem=True))
                            tp[1].set()
                            return msg.ok()
                        elif 'dlid' in self.status and self.status['dlid'] == x:
                            self.osc_c.send_message('/haltjob', 1)
                            return msg.ok()
                        else:
                            ev = Event()
                            self.dl_q[k] = (msg, ev)
                            await ev.wait()
                            del self.dl_q[k]
                    if not msg.f('rem'):
                        format = msg.f('fmt')
                        conv = msg.f('conv')
                        host = msg.f('host')
                        if 'audio' in format:
                            kw = dict(extractaudio=True,
                                      addmetadata=True,
                                      embedthumbnail=True,
                                      postprocessors=[dict(key='FFmpegExtractAudio')])
                        else:
                            kw = dict()
                        ytdl_opt = dict(
                            format=format,
                            noplaylist=True,
                            ignoreerrors=True,
                            outtmpl=join(self.dl_dir, f'{x}_t.%(ext)s'),
                            **kw
                        )
                        self.status['dlid'] = x
                        self.status['dl'] = dict()
                        self.status['dlx'] = dict()
                        await executor(self.processDlOpenAndWait, await self.processDlInitOSCClientServer((it.get_conv_link(host, conv), ytdl_opt)))
                        if 'sta' in self.status['dl'] and not self.status['dl']['sta'] and\
                           'file' in self.status['dl'] and self.status['dl']['file'] and\
                           'rv' in self.status['dlx'] and not self.status['dlx']['rv']:
                            try:
                                remove(it.dl)
                            except Exception:
                                pass
                            rv_err = self.status['dlx']
                            if 'raw' in rv_err and 'requested_downloads' in rv_err['raw'] and\
                               rv_err['raw']['requested_downloads'] and\
                               'filepath' in rv_err['raw']['requested_downloads'][0] and\
                               rv_err['raw']['requested_downloads'][0]['filepath']:
                                fromfile = rv_err['raw']['requested_downloads'][0]['filepath']
                            else:
                                fromfile = self.status['dl']['file']
                            _, ext = splitext(fromfile)
                            it.dl = join(self.dl_dir, f'{x}{ext}')
                            rename(fromfile, it.dl)
                            if not await it.toDB(self.db):
                                msg = msg.err(2, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                            else:
                                msg = msg.ok(playlistitem=it)
                        else:
                            if 'dl' in self.status and 'files' in self.status['dl']:
                                i = self.status['dl']['file']
                                try:
                                    remove(i)
                                except Exception:
                                    pass
                                for i in self.status['dl']['files']:
                                    try:
                                        remove(i)
                                    except Exception:
                                        pass
                            msg = msg.err(5, MSG_BACKEND_ERROR, playlistitem=None)
                        self.osc_t.close()
                        self.osc_s = None
                        self.status['dlid'] = -1
                    else:
                        msg = msg.err(100, MSG_TASK_ABORT, playlistitem=None)
                    if len(self.dl_q) and ('dlid' not in self.status or self.status['dlid'] == -1):
                        next(iter(self.dl_q.items()))[1][1].set()
                    return msg
                else:
                    return msg.err(4, MSG_PLAYLIST_NOT_FOUND, playlistitem=None)
            else:
                return msg.err(3, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
        elif self.osc_s:
            for _, i in self.dl_q.items():
                i[0].set_from_dict(dict(rem=True))
            self.osc_c.send_message('/haltjob', 1)
            return msg.ok()

    async def processIOrder(self, msg, userid, executor):
        x = msg.playlistItemId()
        if x is not None:
            it = await PlaylistItem.loadbyid(self.db, rowid=x)
            if it:
                pls = await Playlist.loadbyid(self.db, rowid=it.playlist, loaditems=LOAD_ITEMS_ALL)
                if pls:
                    pl = pls[0]
                    items = pl.items
                    if pl.useri != userid:
                        return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                    dest_iorder = msg.f("iorder")
                    round_iorder = dest_iorder if (dest_iorder % 10) == 0 else (dest_iorder // 10 + 1) * 10
                    plus_idx = -1
                    # await pl.cleanItems(self.db, commit=False)
                    for idx, other_it in enumerate(items):
                        if other_it.rowid != x and other_it.iorder >= dest_iorder:
                            plus_idx = idx
                            break
                    fix_order = False
                    if plus_idx >= 0:
                        _LOGGER.debug(f"PlusIdx {plus_idx}")
                        cur_iorder = round_iorder + (len(items) - plus_idx) * 10
                        for idx in range(len(items) - 1, plus_idx - 1, -1):
                            _LOGGER.debug(f"SetIorder {items[idx]} -> {cur_iorder}")
                            if not await items[idx].setIOrder(self.db, -cur_iorder, commit=False):
                                return msg.err(5, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                            items[idx].iorder = -items[idx].iorder
                            cur_iorder -= 10
                            fix_order = True
                    if await it.setIOrder(self.db, round_iorder, commit=not fix_order):
                        if fix_order and not await pl.fix_iorder(self.db, commit=fix_order):
                            return msg.err(6, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                        else:
                            return msg.ok(playlistitem=it)
                    else:
                        return msg.err(2, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                else:
                    msg.err(4, MSG_PLAYLIST_NOT_FOUND, playlistitem=None)
            else:
                return msg.err(3, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
        else:
            return msg.err(1, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)

    async def processDel(self, msg, userid, executor):
        x = msg.playlistId()
        if x is not None:
            pls = await Playlist.loadbyid(self.db, rowid=x, loaditems=LOAD_ITEMS_NO)
            if pls:
                if pls[0].useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                res = await pls[0].delete(self.db)
                if res:
                    return msg.ok(playlist=x)
                else:
                    msg.err(2, MSG_PLAYLIST_NOT_FOUND, playlist=None)
            else:
                msg.err(3, MSG_PLAYLIST_NOT_FOUND, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processSort(self, msg, userid, executor):
        x = msg.playlistId()
        if x is not None:
            pls = await Playlist.loadbyid(self.db, rowid=x, loaditems=LOAD_ITEMS_ALL, sort_item_field='datepub')
            if pls:
                pl = pls[0]
                if pl.useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                # await pl.cleanItems(self.db, commit=False)
                cur_iorder = 10
                for other_it in pl.items:
                    if not await other_it.setIOrder(self.db, -cur_iorder, commit=False):
                        return msg.err(5, MSG_PLAYLISTITEM_NOT_FOUND, playlistitem=None)
                    other_it.iorder = -other_it.iorder
                    cur_iorder += 10
                if pl.items:
                    if not await pl.fix_iorder(self.db, commit=True):
                        return msg.err(2, MSG_PLAYLIST_NOT_FOUND, playlist=None)
                    items = pl.items
                    for idx in range(len(items) - 1, -1, -1):
                        other_it = items[idx]
                        if other_it.seen:
                            del items[idx]
                return msg.ok(playlist=pl)
            else:
                msg.err(3, MSG_PLAYLIST_NOT_FOUND, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processPlayId(self, msg, userid, executor):
        x = msg.playlistId()
        if x is not None:
            pls = await Playlist.loadbyid(self.db, rowid=x, loaditems=LOAD_ITEMS_NO)
            if pls:
                pl = pls[0]
                if pl.useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                # await pl.cleanItems(self.db, commit=False)
                play = pl.conf.get('play', dict())
                pl.conf['play'] = play
                play['id'] = msg.f('playid')
                rv = await pl.toDB(self.db)
                if not rv:
                    return msg.err(20, MSG_INVALID_PARAM, playlist=None)
                return msg.ok(playlist=pl)
            else:
                return msg.err(3, MSG_PLAYLIST_NOT_FOUND, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def processPlaySett(self, msg, userid, executor):
        x = msg.playlistId()
        if x is not None:
            pls = await Playlist.loadbyid(self.db, rowid=x, loaditems=LOAD_ITEMS_NO)
            if pls:
                pl = pls[0]
                if pl.useri != userid:
                    return msg.err(501, MSG_UNAUTHORIZED, playlist=None)
                # await pl.cleanItems(self.db, commit=False)
                try:
                    play = pl.conf.get('play', dict())
                    pl.conf['play'] = play
                    play['id'] = msg.f('playid')
                    keys = msg.f('key')
                    oldkeys = msg.f('oldkey')
                    cont = msg.f('content')
                    if cont:
                        key = play.get(keys if not oldkeys else oldkeys, dict())
                        if oldkeys and oldkeys in play and keys != oldkeys:
                            del play[oldkeys]
                        play[keys] = key
                        if 'default' not in key or msg.f('default'):
                            key['default'] = cont
                        key[msg.f('set')] = cont
                    elif cont is not None:
                        play[keys] = dict()
                    elif keys in play:
                        del play[keys]
                    pls = await Playlist.loadbyid(self.db, useri=userid, loaditems=LOAD_ITEMS_NO)
                    for plt in pls:
                        if plt.rowid != x:
                            play = plt.conf.get('play', dict())
                            plt.conf['play'] = play
                            if cont is None:
                                if keys in play:
                                    del play[keys]
                                    await plt.toDB(self.db, commit=False)
                            elif keys not in play or (oldkeys and oldkeys in play and keys != oldkeys):
                                newconf = dict()
                                if oldkeys and oldkeys in play:
                                    newconf = play[oldkeys]
                                    del play[oldkeys]
                                play[keys] = newconf
                                await plt.toDB(self.db, commit=False)
                    rv = await pl.toDB(self.db)
                    if not rv:
                        return msg.err(20, MSG_INVALID_PARAM, playlist=None)
                    return msg.ok(playlist=pl)
                except Exception:
                    _LOGGER.error(traceback.format_exc())
                    return msg.err(30, MSG_INVALID_PARAM, playlist=None)
            else:
                return msg.err(3, MSG_PLAYLIST_NOT_FOUND, playlist=None)
        else:
            return msg.err(1, MSG_PLAYLIST_NOT_FOUND, playlist=None)

    async def process(self, ws, msg, userid, executor):
        resp = None
        if msg.c(CMD_DEL):
            resp = await self.processDel(msg, userid, executor)
        elif msg.c(CMD_MOVE):
            resp = await self.processMove(msg, userid, executor)
        elif msg.c(CMD_PLAYID):
            resp = await self.processPlayId(msg, userid, executor)
        elif msg.c(CMD_PLAYSETT):
            resp = await self.processPlaySett(msg, userid, executor)
        elif msg.c(CMD_PLAYITSETT):
            resp = await self.processPlayItSett(msg, userid, executor)
        elif msg.c(CMD_ADD):
            resp = await self.processAdd(msg, userid, executor)
        elif msg.c(CMD_REN):
            resp = await self.processRen(msg, userid, executor)
        elif msg.c(CMD_DUMP):
            resp = await self.processDump(msg, userid, executor)
        elif msg.c(CMD_SEEN):
            resp = await self.processSeen(msg, userid, executor)
        elif msg.c(CMD_IORDER):
            resp = await self.processIOrder(msg, userid, executor)
        elif msg.c(CMD_DOWNLOAD):
            resp = await self.processDl(msg, userid, executor)
        elif msg.c(CMD_SORT):
            resp = await self.processSort(msg, userid, executor)
        elif msg.c(CMD_CLOSE):
            if ws is not None:
                await ws.close()
        if resp:
            if ws is not None:
                await ws.send_str(json.dumps(resp, cls=MyEncoder))
            return resp
        else:
            return None
