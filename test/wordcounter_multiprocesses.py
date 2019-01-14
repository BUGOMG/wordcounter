#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import operator
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from functools import reduce
from multiprocessing import Pool, cpu_count

import chardet

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
from utils import humansize, humantime, processbar  # noqa


def wrap(wordcounter, fn, p1, p2, f_size):
    return wordcounter.count_multi(fn, p1, p2, f_size)


class WordCounter(object):
    def __init__(self, from_file, to_file=None, workers=None, coding=None):
        if not os.path.isfile(from_file):
            raise Exception("文件不存在")
        self.f1 = from_file
        self.filesize = os.path.getsize(from_file)
        self.f2 = to_file
        self.workers = workers if workers is not None else cpu_count() * 64
        if coding is None:
            with open(from_file, "rb") as fp:
                coding = chardet.detect(fp.read(1000))["encoding"]
        self.coding = coding
        self._c = Counter()

    def run(self):
        start = time.time()
        if self.workers == 0:
            self.count_direct(self.f1)
        elif self.workers == 1:
            self.count_single(self.f1, self.filesize)
        else:
            pool = Pool(self.workers)
            res_list = []
            for i in range(self.workers):
                p1 = self.filesize * i // self.workers
                p2 = self.filesize * (i + 1) // self.workers
                args = [self, self.f1, p1, p2, self.filesize]
                res = pool.apply_async(func=wrap, args=args)
                res_list.append(res)
            pool.close()
            pool.join()
            self._c.update(reduce(operator.add, [r.get() for r in res_list]))
        if self.f2:
            with open(self.f2, "wb") as fp:
                fp.write(self.result.encode(self.coding))
        else:
            print(self.result)
        cost = time.time() - start
        cost = "{:.1f} seconds".format(cost) if cost < 60 else humantime(cost)
        size = humansize(self.filesize)
        tip = "\nFile size: {}. Workers: {}. Cost time: {}"
        print(tip.format(size, self.workers, cost))
        self.cost = cost + "s"

    def count_direct(self, from_file):
        """直接把文件内容全部读进内存并统计词频"""
        with open(from_file, "rb") as fp:
            line = fp.read()
        self._c.update(self.parse(line))

    def count_single(self, from_file, f_size):
        """单进程读取文件并统计词频"""
        start = time.time()
        with open(from_file, "rb") as fp:
            for line in fp:
                self._c.update(self.parse(line))
                processbar(fp.tell(), f_size, from_file, f_size, start)

    def count_multi(self, fn, p1, p2, f_size):
        c = Counter()
        with open(fn, "rb") as fp:
            if p1:  # 为防止字被截断的，分段处所在行不处理，从下一行开始正式处理
                fp.seek(p1 - 1)
                while b"\n" not in fp.read(1):
                    pass
            start = time.time()
            while 1:
                line = fp.readline()
                c.update(self.parse(line))
                pos = fp.tell()
                if p1 == 0:  # 显示进度
                    processbar(pos, p2, fn, f_size, start)
                if pos >= p2:
                    return c

    def parse(self, line):  # 解析读取的文件流
        return Counter(re.sub(r"\s+", "", line.decode(self.coding)))

    def flush(self):
        self._c = Counter()

    @property
    def counter(self):
        return self._c

    @property
    def result(self):
        ss = ["{}: {}".format(i, j) for i, j in self._c.most_common()]
        return "\n".join(ss)  # .decode(self.coding)


def main():
    if len(sys.argv) > 2:
        from_file, to_file = sys.argv[1:3]
    # 在上一级目录的var文件夹中，生成测试用大文件
    if os.path.dirname(__file__) in ["test"]:
        dir_of_bigfile = os.path.join("..", "var")
    else:
        dir_of_bigfile = "var"
    if not os.path.exists(dir_of_bigfile):
        os.mkdir(dir_of_bigfile)
    from_file, to_file = "100lines.txt", "count_result.txt"

    with open(from_file, "rb") as fp:
        s = fp.read()
    files = []
    for i in [2000, 10000, 20000, 100000, 200000]:
        fn = "{}thousandlines.txt".format(i // 10)
        ffn = os.path.join(dir_of_bigfile, fn)
        files.append(ffn)
        if not os.path.exists(ffn):
            with open(ffn, "wb") as fp:
                fp.write(s * i)

    ps = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]  # 待测试的进程数
    pre = "{:8}" * (len(ps) + 1)
    title = ["size"] + ["{}ps".format(i) for i in ps]
    L = [pre.format(*title)]
    for i in files:
        size = os.path.getsize(i)
        ws = [WordCounter(i, to_file, p) for p in ps]
        [w.run() for w in ws]
        title = [humansize(size)] + [w.cost for w in ws]
        L.append(pre.format(*title))
        print("-" * 40)
    t = "cpu_count = {}, now = {}".format(cpu_count(), datetime.now())
    result = "\n".join([sys.version, t] + L + ["-" * 75, ""])
    print(result)
    with open("test_result.txt", "ab") as fp:
        fp.write(result.encode("utf-8"))


if __name__ == "__main__":
    main()
