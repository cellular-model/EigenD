
#
# Copyright 2009 Eigenlabs Ltd.  http://www.eigenlabs.com
#
# This file is part of EigenD.
#
# EigenD is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# EigenD is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EigenD.  If not, see <http://www.gnu.org/licenses/>.
#

import wx
import picross
import piw
import random
import optparse
import sys

from pi import atom,action,node,domain,logic,bundles,resource,version,agent
from pisession import gui
from pi.logic.shortcuts import T

from pigui import fonts, language
from app_commander import  mainframe,history,command,dictionary,upgrade

class ScrollerDelegate(piw.scrolldelegate):
    def __init__(self,scrollfunc,tapfunc):
        self.__scrollfunc = scrollfunc
        self.__tapfunc=tapfunc
        piw.scrolldelegate.__init__(self)
    def scroll(self,h,v):
        if self.__scrollfunc:
            self.__scrollfunc(h,v)
    def tap(self):
        if self.__tapfunc:
            self.__tapfunc()

class Scroller(piw.scroller):
    def __init__(self,func1,func2):
        self.__delegate = ScrollerDelegate(func1,func2)
        piw.scroller.__init__(self,self.__delegate,0.5,0.5,100)

class ViewManager(agent.Agent):

    def __init__(self,name):
        agent.Agent.__init__(self,signature=upgrade.Signature(),volatile=True,names='eigencommander',ordinal=1)

        self.name = name
        self.node = random.randrange(0, 1<<48L) | 0x010000000000L

        self.langModel=gui.call_bg_sync(self.__create_lang)
        self.historyModel=history.HistoryModel(self.langModel)
        self.commandModel=command.CommandModel(self.langModel)
        self.cdomain = piw.clockdomain_ctl()
        self.cdomain.set_source(piw.makestring('*',0))

        self.scroller1 = Scroller(self.__scroll1,self.__tap1) # scrolls the dictionary pane
        self.scroller2 = Scroller(self.__scroll2,self.__tap2) # scrolls the history pane
        self.scroller3 = Scroller(self.__scroll3,self.__tap3) # empty

        self.scroller_in1 = bundles.VectorInput(self.scroller1.cookie(),self.cdomain,signals=(1,2,3))
        self.scroller_in2 = bundles.VectorInput(self.scroller2.cookie(),self.cdomain,signals=(1,2,3))
        self.scroller_in3 = bundles.VectorInput(self.scroller3.cookie(),self.cdomain,signals=(1,2,3))

        nudge=(T('inc',0.1),)
        self[1] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=0, names='sideways nudger', ordinal=1, policy=self.scroller_in1.vector_policy(1,False))
        #self[2] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=0, names='vertical nudger', ordinal=1, policy=self.scroller_in1.vector_policy(2,False),rtransient=True)
        self[2] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=0, names='vertical nudger', ordinal=1, policy=self.scroller_in1.vector_policy(2,False))


        self[3] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=0, names='sideways nudger', ordinal=2, policy=self.scroller_in2.vector_policy(1,False))
        self[4] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=0, names='vertical nudger', ordinal=2, policy=self.scroller_in2.vector_policy(2,False))

        #self[8]=browse.BrowseAgent(self,browse.getName())

        self[9]=dictionary.DictionaryAgent(self,dictionary.getName())
#        self.add_verb2(1,'browse([],None,role(None,[proto(browse),singular]))',callback=self.__do_browse)
        self.add_verb2(2,'minimise([],None)',callback=self.__minimise)
        self.add_verb2(3,'maximise([],None)',callback=self.__maximise)
        
        self.font=wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.font.SetPointSize(fonts.DEFAULT_PTS)

        self[12]=atom.Atom(domain=domain.BoundedInt(5,20,rest=11),names='text',policy=atom.default_policy(self.__set_fontsize))
        self[15] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=-1, names='sideways nudger', ordinal=3, policy=self.scroller_in3.vector_policy(1,False))
        self[16] = atom.Atom(domain=domain.BoundedFloat(-1,1,hints=nudge), init=-1, names='vertical nudger', ordinal=3, policy=self.scroller_in3.vector_policy(2,False))
        self[17] = atom.Atom(domain=domain.BoundedFloat(0,1), init=0, names='tapper', ordinal=1, policy=self.scroller_in1.vector_policy(3,False))
        self[18] = atom.Atom(domain=domain.BoundedFloat(0,1), init=0, names='tapper', ordinal=2, policy=self.scroller_in2.vector_policy(3,False))
        self[19] = atom.Atom(domain=domain.BoundedFloat(0,1), init=0, names='tapper', ordinal=3, policy=self.scroller_in3.vector_policy(3,False))

        self.__size=node.Server(change=self.__size_changed)
        self.set_private(node.Server())
        self.get_private()[1]=self.__size
        self.__x=100
        self.__y=100
        self.__setup_size()

        self.__minX=60
        self.__minY=80
        self.__maxX=100
        self.__maxY=100

        self.__rootFrame=None
        self.__createRootFrame()

        self.scroller1.reset(1,-1)
#        self.scroller3.reset(-1,-1)
        self.scroller2.reset(-1,1)
#        self.scroller1.set_scheme(1)

        self.scroller1.enable()
        self.scroller2.enable()
        self.scroller3.enable()

#    def __do_browse(self,subject,*args):
#        print '__do_browse',args
#        #self[8].model.changeTargetArgs(args)

    def __size_changed(self,d):
        print '__size_changed'
        if not d.is_string():
            return False
        l = logic.parse_clause(d.as_string())
        self.__x=l[0]
        self.__y=l[1]
        self.__setup_size()
        if self.__rootFrame:
            self.__doSetSize()

    def __setup_size(self):
        print '__setup_size',self.__x,self.__y
        self.__size.set_data(piw.makestring(logic.render_term((self.__x,self.__y)),0))

    def __create_lang(self):
        return language.LanguageModel()

    def reset1(self,h=None,v=None):
        #print 'reset1:  v=',v
        self.scroller1.reset(h,v*-1)
 
    def reset2(self,h=None,v=None):
        self.scroller2.reset(h,v*-1)
    
    def reset3(self,h=None,v=None):
        self.scroller3.reset(h,v*-1)

    def getTitlePanel(self):
        if self.__rootFrame:
            return self.__rootFrame.getTitlePanel()

    def updateStatus(self,text):
        print 'commander_cli:updateStatus',text
        self.__rootFrame.updateStatus(text)

    def doSize(self):
        print 'doSize'
        if self.__rootFrame:
            size=self.__rootFrame.GetSize()
            screenSize=wx.DisplaySize()
            self.__x=int(100*(float(size[0])/float(screenSize[0])))
            self.__y=int(100*(float(size[1])/float(screenSize[1])))
            print 'doSize',size,screenSize,self.__x,self.__y

            self.__setup_size()

    def __set_fontsize(self, value):
        print '__set_fontsize',value
        self.font=wx.Font(value,wx.FONTFAMILY_SWISS,wx.FONTSTYLE_NORMAL,weight=wx.FONTWEIGHT_NORMAL)
        return True

    def __scroll1(self,h,v):
        print '__scroll1',h,v
        picross.display_active()
        
        #self.__scroll_dict(h,v*-1)
        self.__scroll_dict(h*-1,v)

    def __scroll3(self,h,v):
        picross.display_active()
        #self.__scroll_info(h,v*-1)

    def __scroll2(self,h,v):
        picross.display_active()
        self.__scroll_history(h,v*-1)
    
    def __tap1(self):
        print 'tap 1'
   
    def __tap2(self):
        print 'tap 2'

    def __tap3(self):
        print 'tap 3'

    def onTap3(self):
        pass
 
    def __getDictionaryPanel(self):
        if self.__rootFrame:
            return self.__rootFrame.getDictionaryPanel()
     
    def __getInfoPanel(self):
        if self.__rootFrame:
            return self.__rootFrame.getInfoPanel()
    
    def __getHistoryPanel(self):
        if self.__rootFrame:
            return self.__rootFrame.getHistoryPanel()

    def __minimise(self,*args):
        self.__x=self.__minX
        self.__y=self.__minY
        self.__setup_size()
        self.__doSetSize()

    def __doSetSize(self):
        size=wx.DisplaySize()
        size=(  (0.01*self.__x*size[0])-10 , (0.01*self.__y*size[1])-50   )
        self.__rootFrame.SetSize(size)

    def __maximise(self,*args):
        self.__x=self.__maxX
        self.__y=self.__maxY
        self.__setup_size()
        self.__doSetSize()

    def __scroll_dict(self,h,v):
        vp=self.__getDictionaryPanel()
        if vp:
            #print '__scroll_list: v=',v
            vp.test_scroll_both(h,v)
    
    def __scroll_history(self,h,v):
        vp=self.__getHistoryPanel()
        if vp:
            vp.scroll_both(h,v)

    def __scroll_info(self,h,v):
        vp=self.__getInfoPanel()
        if vp:
            vp.scroll_both(h,v)


    def __createRootFrame(self):
        size=wx.DisplaySize()
        size=(  (size[0]-10),(size[1]-50)   )
        self.__rootFrame=mainframe.MainFrame('',self,size)

        self.__rootFrame.Show()
        self.updateStatus('Connecting...')
        self.__doSetSize()
    
#    def doHints(self,hints):
#        pass
#        view,target=logic.parse_clause(hints[0])
#        print 'Browser:doHints',view,target
#        if view=='browseview':
#            self[8].model.change_target(target)
#        else:
#            print 'No hint'

    def getMainFrame(self):
        return self.__rootFrame

class commanderApp(gui.App):
    def __init__(self,name,logfunc):
        gui.App.__init__(self,logfunc=logfunc,name=name)
#        gui.App.__init__(self,name=name)
        print 'commander starting'
        imageName=resource.find_release_resource('app_commander','commander_splash.png')
        if imageName:
            image=wx.Image(imageName,wx.BITMAP_TYPE_PNG)
            bmp=image.ConvertToBitmap()
            wx.SplashScreen(bmp,wx.SPLASH_CENTRE_ON_SCREEN|wx.SPLASH_TIMEOUT,2000,None,-1)
            wx.Yield()
        print 'commander starting 2'
        self.agent = ViewManager(name)
        print 'commander starting 3'
        piw.tsd_server('<%s>' % name, self.agent)
        print 'commander starting 4'
        self.agent.advertise('<main>')
        print 'commander starting 5'

def cli():
    parser = optparse.OptionParser()
    parser.add_option('--stdout',action='store_true',dest='stdout',default=False,help='log to stdout')

    x = [ a for a in sys.argv if not a.startswith('-psn') ]
    (opts,args) = parser.parse_args(x)

    name = 'eigencommander1'

    lock = resource.LockFile(name)
    if not lock.lock():
        print 'cannot get lock: aborting'
        sys.exit(-1)

    if opts.stdout:
        logfile=sys.__stdout__
    else:
        logfile=resource.open_logfile(name)

    def logger(msg):
        print >>logfile,name,msg
        logfile.flush()

    app=commanderApp(name,logfunc=logger)
    app.MainLoop()
    picross.exit(0)