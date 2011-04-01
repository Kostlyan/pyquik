# -*- coding: utf-8 -*-
from .order import Order, BUY, SELL, MARKET_PRICE
from talib.talib import TA_LIB, TA_Func
import numpy,datetime


ta_lib = TA_LIB()

class Serie:

    ALLOC_BLOCK=1024

    def __init__(self,ticker, name, dtype=numpy.float):
        self.ticker = ticker
        self.name = name
        self.size = 0
        self.buf = numpy.array([], dtype=dtype)

    def push(self, value):
        if self.size >= len(self.buf):
            self.buf.resize( self.size + Serie.ALLOC_BLOCK )
        self.buf[ self.size ] = value
        self.size += 1

    def data(self):
        return self.buf[:self.size]

class Indicator(Serie):

    def __init__(self,ticker, name, **kwargs):
        Serie.__init__(self,ticker,name)
        self.func = ta_lib.func( name )
        self.kwa = kwargs
        src = self.ticker("price").data()
        src_len = len(src)
        if src_len:
            self.buf.resize( src_len )
            self.size = src_len
            shift, num = self.func(0, src_len-1, src, self.buf)
            self.buf = numpy.roll( self.buf, shift )

    def push(self,value):
        Serie.push( self, 0.0 )
        src = self.ticker("price").data()
        idx = self.size-1
        self.func(idx, idx, src, self.buf[idx:], **self.kwa)

 
class Ticker:

    FIELDS =['seccode','classcode']

    SERIES = ['time','price','volume']

    def __init__(self,factory,name):
        self.factory = factory
        self.seccode = name
        self.classcode = False
        self.series = {}
        self.orders = []
        for name in Ticker.SERIES:
            self.series[ name ] = Serie(self,name,dtype=(numpy.float if name != 'time' else datetime.datetime))

    def __iter__(self):
        return serie.__iter__()

    def __call__(self,name,stype=Serie, **kwargs):
        if name in self.series:
            return self.series[name]
        serie = self.series[name] = Indicator( self, name, **kwargs )
        return serie

    def buy(self,price=MARKET_PRICE,quantity=1):
        o = Order(self,BUY, price, quantity)
        self.orders.append(o)
        o.submit()
        return o

    def sell(self,price=MARKET_PRICE,quantity=1):
        o = Order(self, SELL, price, quantity)
        self.orders.append(o)
        o.submit()
        return o

    def tick(self):
        for name in self.series:
            self.series[name].push( getattr( self, name, None ) )

    def __repr__(self):
        return ";".join( [ "%s=%s" % ( x.upper(), getattr( self, x) ) for x in (Ticker.FIELDS + Ticker.SERIES) ]  )

class TickerFactory:

    def __init__(self, quik):
        self.quik    = quik
        self.tickers = {}
        self.headers = False

    def __call__(self, name):
        return self.__getattr__(name)

    def __getattr__(self, name):
        if name in self.tickers:
            return self.tickers[ name ]
        ticker = self.tickers[ name ] = Ticker( self, name )
        return ticker

    def update( self, table, r ):
        ticker = self(table.getString(r,self.headers.index("Код бумаги")))
        if not ticker.classcode:
            ticker.classcode = table.getString(r,self.headers.index("Код класса"))

        ticker.time = datetime.datetime.now()
        ticker.price =  float(table.getDouble(r,self.headers.index("Цена послед.")))
        ticker.volume = int(table.getDouble(r,self.headers.index("Оборот")))
        ticker.tick()
        if hasattr( self.quik, "onTicker" ):
            self.quik.onTicker( ticker )

    def load(self, filename):
        fp = open( filename )
        try:
            headers = fp.readline().rstrip().split(',')
            IDX_TICKER = headers.index( '<TICKER>' )
            IDX_DATE = headers.index( '<DATE>' )
            IDX_TIME = headers.index( '<TIME>' )
            IDX_LAST = headers.index( '<LAST>' )
            IDX_VOL  = headers.index( '<VOL>' )
            while True:
                line = fp.readline()
                if not line: break
                row = line.rstrip().split(',')
                ticker = self( row[ IDX_TICKER ] )
                ticker.time = datetime.datetime.strptime(row[ IDX_DATE ]+row[ IDX_TIME ], '%Y%m%d%H%M%S')
                ticker.price = float(row[ IDX_LAST ])
                ticker.volume = float(row[ IDX_VOL ])
                ticker.tick()
        finally:
            fp.close()