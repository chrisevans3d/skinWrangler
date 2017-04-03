'''
skinWrangler
Christopher Evans, Version 2.0, July 2014
@author = Chris Evans
version = 2.0
TODO
- if a joint is selected and zeroed out, don't keep it selected on refresh and focus on it
- throw warning if every inf in the active list is selected to be zeroed out
- figure out a way to color mesh from joint influence colors
- better skin mirror with friggin feedback as to what points aren't found
Add this to a shelf:
import skinWrangler as sw
skinWranglerWindow = sw.show()
'''

import os

from Qt import QtGui, QtWidgets
from cStringIO import StringIO
import xml.etree.ElementTree as xml

import maya.cmds as cmds
import maya.OpenMayaUI as openMayaUI
import maya.mel as mel

mayaApi = cmds.about(api=True)
if mayaApi >= 201700:
    import shiboken2 as shiboken
    import pyside2uic as pysideuic
else:
    import shiboken
    import pysideuic

def show():
    global skinWranglerWindow
    try:
        skinWranglerWindow.close()
    except:
        pass

    skinWranglerWindow = skinWrangler()
    skinWranglerWindow.show()
    return skinWranglerWindow

def loadUiType(uiFile):
    """
    Pyside lacks the "loadUiType" command, so we have to convert the ui file to py code in-memory first
    and then execute it in a special frame to retrieve the form_class.
    http://tech-artists.org/forum/showthread.php?3035-PySide-in-Maya-2013
    """
    parsed = xml.parse(uiFile)
    widget_class = parsed.find('widget').get('class')
    form_class = parsed.find('class').text

    with open(uiFile, 'r') as f:
        o = StringIO()
        frame = {}

        pysideuic.compileUi(f, o, indent=0)
        pyc = compile(o.getvalue(), '<string>', 'exec')
        exec pyc in frame

        #Fetch the base_class and form class based on their type in the xml from designer
        print form_class + ' - ' + widget_class
        form_class = frame['Ui_%s'%form_class]
        base_class = eval('QtWidgets.%s'%widget_class)

    return form_class, base_class

def getMayaWindow():
    ptr = openMayaUI.MQtUtil.mainWindow()
    if ptr is not None:
        return shiboken.wrapInstance(long(ptr), QtWidgets.QWidget)

uiFile = None 
try:
    selfDirectory = os.path.dirname(__file__)
    uiFile = selfDirectory + '/skinWrangler.ui'
except:
    uiFile = 'D:\\Build\\usr\\jeremy_ernst\\MayaTools\\General\\Scripts\\epic\\rigging\\skinWrangler\\skinWrangler.ui'
if os.path.isfile(uiFile):
    form_class, base_class = loadUiType(uiFile)
else:
    cmds.error('Cannot find UI file: ' + uiFile)



########################################################################
## SKIN WRANGLER
########################################################################
       

class skinWrangler(base_class, form_class): 
    title = 'skinWrangler 2.0'
    
    currentMesh = None
    currentSkin = None
    currentInf = None
    currentVerts = None
    currentNormalization = None
    
    scriptJobNum = None
    copyCache = None
    
    jointLoc = None
    
    iconLib = {}
    iconPath = os.environ.get('MAYA_LOCATION', None) + '/icons/'
    iconLib['joint'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'kinJoint.png'))
    iconLib['ikHandle'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'kinHandle.png'))
    iconLib['transform'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'orientJoint.png'))
    
    def __init__(self, parent=getMayaWindow()):
        self.closeExistingWindow()
        super(skinWrangler, self).__init__(parent)
        
        self.setupUi(self)
        self.setWindowTitle(self.title)
        
        wName = openMayaUI.MQtUtil.fullName(long(shiboken.getCppPointer(self)[0]))

        ## Connect UI
        ########################################################################
        self.refreshBTN.clicked.connect(self.refreshUI)
        
        #selection buttons
        self.selShellBTN.clicked.connect(self.selShellFn)
        self.selGrowBTN.clicked.connect(self.selGrowFn)
        self.selShrinkBTN.clicked.connect(self.selShrinkFn)
        self.selLoopBTN.clicked.connect(self.selLoopFn)
        self.selPointsEffectedBTN.clicked.connect(self.selPointsEffectedFn)

        #weight buttons
        self.weightZeroBTN.clicked.connect(self.weightZeroFn)
        self.weightHalfBTN.clicked.connect(self.weightHalfFn)
        self.weightFullBTN.clicked.connect(self.weightFullFn)
        self.setWeightBTN.clicked.connect(self.setWeightFn)
        self.plusWeightBTN.clicked.connect(self.plusWeightFn)
        self.minusWeightBTN.clicked.connect(self.minusWeightFn)
        self.copyBTN.clicked.connect(self.copyFn)
        self.pasteBTN.clicked.connect(self.pasteFn)
        self.selectVertsWithInfBTN.clicked.connect(self.selectVertsWithInfFn)
        self.setAverageWeightBTN.clicked.connect(self.setAverageWeightFn)

        #callbacks on state change
        self.jointLST.itemSelectionChanged.connect(self.jointListSelChanged)
        self.listAllCHK.stateChanged.connect(self.listAllChanged)
        self.nameSpaceCHK.stateChanged.connect(self.cutNamespace)
        self.skinNormalCMB.currentIndexChanged.connect(self.skinNormalFn)

        #tree filter
        self.filterLINE.returnPressed.connect(self.refreshUI)
        self.filterBTN.clicked.connect(self.refreshUI)

        #SKIN UTILS TAB:
        self.clampInfBTN.clicked.connect(self.clampInfFn)
        self.bindPoseBTN.clicked.connect(self.bindPoseFn)
        self.removeUnusedBTN.clicked.connect(self.removeUnusedFn)
        self.addJntBTN.clicked.connect(self.addJntFn)
        
        #TOOLS TAB
        self.jointOnBboxCenterBTN.clicked.connect(self.jointOnBboxCenterFn)
        self.rigidShellsBtn.clicked.connect(self.rigidShellsFn)

        self.scriptJobNum = cmds.scriptJob(e=['SelectionChanged', 'skinWranglerWindow.refreshUI()'], kws=1)
        print 'skinWrangler initialized as', wName, 'scriptJob:', self.scriptJobNum
        self.refreshUI()
        
    def closeEvent(self, e):
        if self.scriptJobNum:
            print '[skinWrangler] Killing scriptJob (' + str(self.scriptJobNum) + ')'
            cmds.scriptJob( kill=self.scriptJobNum, force=1)
            self.scriptJobNum = None
        self.removeAnnotations()
    
    def closeExistingWindow(self):
        for qt in QtWidgets.QApplication.topLevelWidgets():
            try:
                if qt.__class__.__name__ == self.__class__.__name__:
                    qt.deleteLater()
                    print 'skinWrangler: Closed ' + str(qt.__class__.__name__)
            except:
                pass

    def averageWeights(self, weights):
        total = 0.0
        for w in weights: total += w
        return total/len(weights)
    
    def findRelatedSkinCluster(self, skinObject):
        '''Python implementation of MEL command: http://takkun.nyamuuuu.net/blog/archives/592'''
        
        skinShape = None
        skinShapeWithPath = None
        hiddenShape = None
        hiddenShapeWithPath = None
    
        cpTest = cmds.ls( skinObject, typ="controlPoint" )
        if len( cpTest ):
            skinShape = skinObject
    
        else:
            rels = cmds.listRelatives( skinObject )
            if rels == None: return False
            for r in rels :
                cpTest = cmds.ls( "%s|%s" % ( skinObject, r ), typ="controlPoint" )
                if len( cpTest ) == 0:
                    continue
    
                io = cmds.getAttr( "%s|%s.io" % ( skinObject, r ) )
                if io:
                    continue
    
                visible = cmds.getAttr( "%s|%s.v" % ( skinObject, r ) )
                if not visible:
                    hiddenShape = r
                    hiddenShapeWithPath = "%s|%s" % ( skinObject, r )
                    continue
    
                skinShape = r
                skinShapeWithPath = "%s|%s" % ( skinObject, r )
                break
    
        if skinShape:
            if len( skinShape ) == 0:
                if len( hiddenShape ) == 0:
                    return None
        
                else:
                    skinShape = hiddenShape
                    skinShapeWithPath = hiddenShapeWithPath
    
        clusters = cmds.ls( typ="skinCluster" )
        for c in clusters:
            geom = cmds.skinCluster( c, q=True, g=True )
            for g in geom:
                if g == skinShape or g == skinShapeWithPath:
                    return c
    
        return None
    
    #annotation
    def removeAnnotations(self):
        annos = cmds.ls('SKINWRANGLER_ANNO_*')
        if annos:
            cmds.delete(annos)

    def annotateNodes(self, nodes):
        '''
        Annotate each node with it's name
        '''
        for node in nodes:
            anno = cmds.createNode('annotationShape', n='SKINWRANGLER_ANNO', ss=1)
            cmds.setAttr(anno + '.text', node, type='string')
            annoXform = cmds.listRelatives(anno, parent=1)
            cmds.pointConstraint(node, annoXform)
            cmds.setAttr(anno + '.displayArrow', False)
            cmds.rename(annoXform, 'SKINWRANGLER_ANNO_XFORM')

            
    ## GET FROM SCENE
    ########################################################################
    def getSelected(self):
        #check to make sure a mesh is selected
        msh = cmds.ls(sl=1, o=1, type='mesh')
        if msh:
            skin = self.findRelatedSkinCluster(msh[0])
            if not skin:
                cmds.warning('Cannot find a skinCluster related to [' + msh + ']')
                return False
            self.currentSkin = skin
            self.currentMesh = msh[0]
            cmds.selectMode(component=1)
            sel = cmds.ls(sl=1, flatten = 1)
            if sel:
                msh = msh[0]
                vtx = None
                if sel != msh:
                    if sel:
                        vtx = len(sel)
                    else: vtx = 0
                self.currentVerts = sel
                
                return sel, msh, vtx, skin
        else:
            print('Please select a mesh.')
            return False
    
    def getAvgVertWeights(self, sel, skin):
        '''
        Returns an averaged weight dictionary
        '''
        wDict = {}
        for jnt in cmds.skinCluster(skin, q=1, wi=1):
            amt = cmds.skinPercent(skin, sel, q=1, t=jnt)
            if amt > 0.0: wDict[jnt] = amt
        return wDict
        
    def vDictToTv(self, wDict):
        re = []
        for inf in wDict.keys():
            re.append((inf, wDict[inf]))
        return re
        
    def skinNormalFn(self, n):
        if n == 0:
            cmds.setAttr(self.currentSkin + '.normalizeWeights', n)
            self.currentNormalization = 'None'
        if n == 1:
            cmds.setAttr(self.currentSkin + '.normalizeWeights', n)
            self.currentNormalization = 'Interactive'
        if n == 2:
            cmds.setAttr(self.currentSkin + '.normalizeWeights', n)
            self.currentNormalization = 'Post'
        self.refreshUI()
    
    ## POLY SELECTION UI
    ########################################################################
    def selGrowFn(self):
        cmds.GrowPolygonSelectionRegion()
    def selShrinkFn(self):
        cmds.ShrinkPolygonSelectionRegion()
    def selShellFn(self):
        cmds.ConvertSelectionToShell()
    def selLoopFn(self):
        cmds.polySelectSp(loop=1)
    def selPointsEffectedFn(self):
        cmds.skinCluster(self.currentSkin, e=1, selectInfluenceVerts=self.currentInf)
    
    
    ## JOINT LIST
    ########################################################################
    #TODO: I believe this callback is getting fired twice per user input
    def jointListSelChanged(self, debug=1):
        #TODO: Need to use/store long paths or API pointers here as extra data on the widgets
        try:
            self.currentWidgets = self.jointLST.selectedItems()
            nodes = [item.text(0) for item in self.currentWidgets]
            if nodes:
                if nodes[0] == 'MAKE A COMPONENT\n SELECTION ON\n SKINNED MESH':
                    self.currentInf = []
                    return None
                
                self.currentInf = nodes
                
                if debug:
                    print self.currentInf
                
                #Annotation
                if self.dynAnnotationCHK.isChecked():
                    self.removeAnnotations()
                    self.annotateNodes(nodes)
                if debug:
                    print self.currentInf
            
        except Exception as e:
            cmds.error(e)

    def getJointFromList(self, jnt):
        for i in range(0, self.jointLST.topLevelItemCount()):
            item = self.jointLST.topLevelItem(i)
            if item.text(0) == jnt: return item
        return False
        
    def listAllChanged(self):
        self.refreshUI()
        
    def cutNamespace(self):
        self.refreshUI()



    ## SKINNING FUNCTIONS
    ########################################################################
    def weightZeroFn(self):
        if self.currentInf:
            for inf in self.currentInf:
                cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[inf, 0.0])
            self.refreshUI()
    
    def weightHalfFn(self):
        if self.currentInf:
            num = len(self.currentInf)
            if num == 1:
                cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[str(self.currentInf[0]), 0.5])
            elif num == 2:
                cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[str(self.currentInf[0]), 1.0])
                cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[str(self.currentInf[1]), 0.5])
            elif num > 2:
                if self.currentNormalization != 'None':
                    cmds.warning('skinWrangler: Cannot skin more than two influences to 0.5 in a normalization mode')
                    return None
                else:
                    for inf in self.currentInf:
                        cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[inf, 0.5])
            self.refreshUI()
    
    def weightFullFn(self):
        if self.currentInf:
            num = len(self.currentInf)
        if num == 1:
            cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[self.currentInf[0], 1.0])
        elif num > 1:
            if self.currentNormalization != 'None':
                cmds.warning('skinWrangler: Cannot skin more than two influences to 1.0 in a normalization mode')
                return None
        self.refreshUI()
    
    def setWeightFn(self):
        if self.currentInf:
            if len(self.currentInf) > 1:
                cmds.warning('skinWrangler: Set Weight does not work with multi-selection because I am too lazy at the moment to write my own normalization code.')
            else:
                cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[self.currentInf[0], self.setWeightSpin.value()])
            self.refreshUI()
        else: cmds.warning('[skinWrangler] No influences/joints selected')
        
    def plusWeightFn(self):
        try:
            cmds.undoInfo(openChunk=True)
            val = self.setWeightSpin.value()
            if self.currentInf:
                for inf in self.currentInf:
                    cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[inf, val], r=1)
            else: cmds.warning('[skinWrangler] No influences/joints selected')
            self.refreshUI()
        except Exception as e:
            print e
        finally:
            cmds.undoInfo(closeChunk=True)
    
    def minusWeightFn(self):
        try:
            cmds.undoInfo(openChunk=True)
            val = -self.setWeightSpin.value()
            if self.currentInf:
                for inf in self.currentInf:
                    cmds.skinPercent(self.currentSkin, self.currentVerts, tv=[inf, val], r=1)
            else: cmds.warning('[skinWrangler] No influences/joints selected')
            self.refreshUI()
        except Exception as e:
            print e
        finally:
            cmds.undoInfo(closeChunk=True)
    
    def copyFn(self):
        if self.copyBTN.isChecked() == True:
            self.copyBTN.setText('WEIGHTS COPIED')
            self.copyBTN.setStyleSheet("background-color: #7a4242")
            self.getSelected()
            self.copyCache = self.getAvgVertWeights(self.currentVerts, self.currentSkin)
            toolTip = ''
            for item in self.copyCache.keys():
                toolTip += (item + ' - ' + str("%.4f" % self.copyCache[item]) + '\n')
            self.copyBTN.setToolTip(toolTip)
        else:
            self.copyBTN.setText('COPY')
            self.copyBTN.setStyleSheet("background-color: #666666")
            self.copyBTN.setToolTip('')
            self.copyCache = None
        
    def pasteFn(self):
        self.getSelected()
        tvTuples = self.vDictToTv(self.copyCache)
        print '[skinWrangler] Pasting weights to current selection: ', tvTuples
        cmds.skinPercent(self.currentSkin, self.currentVerts, tv=tvTuples)
        self.refreshUI()
    
    def selectVertsWithInfFn(self):
        self.checkMaxSkinInfluences(self.currentMesh, self.selectVertsWithInfSPIN.value(), select=1)
    
    def setAverageWeightFn(self):
        try:
            cmds.undoInfo(openChunk=True)
            if not self.avgOptionCHK.isChecked():
                mel.eval('weightHammerVerts;')
            else:
                sel = cmds.ls(sl=1)
                cmds.ConvertSelectionToVertices()
                newSel = cmds.ls(sl=1, flatten=1)
                for vert in newSel:
                    self.setAverageWeight(vert)
                self.clampInfluences(self.currentMesh, self.clampInfSPIN.value(), force=1)
                cmds.select(sel)
        except Exception as e:
            cmds.error('skinWrangler: ' + str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
    
    def setAverageWeight(self, vtx):
        msh = vtx.split('.')[0]
        cmds.select(vtx)
        cmds.ConvertSelectionToEdges()
        cmds.ConvertSelectionToVertices()
        neighbors = cmds.ls(sl=1, flatten=1)
        neighbors.pop(neighbors.index(vtx))
        infList = {}
        skin = self.findRelatedSkinCluster(msh)
        for vert in neighbors:
            for jnt in cmds.skinCluster(skin, q=1, wi=1):
                amt = cmds.skinPercent(skin, vert, q=1, t=jnt)
                if amt > 0.0:
                    if jnt in infList: infList[jnt].append(amt)
                    else: infList[str(jnt)] = [amt]
        for inf in infList:
            total = None
            for w in infList[inf]:
                if not total: total = w
                else: total += w
            weight = total/len(infList[inf])
            cmds.skinPercent(self.currentSkin, vtx, tv=[str(inf), weight], nrm=1)
    
    def checkMaxSkinInfluences(self, node, maxInf, debug=1, select=0):
        '''Takes node name string and max influences int.
        From CG talk thread (MEL converted to Python, then added some things)'''
        
        cmds.select(cl=1)
        skinClust = self.findRelatedSkinCluster(node)
        if skinClust == "": cmds.error("checkSkinInfluences: can't find skinCluster connected to '" + node + "'.\n");
    
        verts = cmds.polyEvaluate(node, v=1)
        returnVerts = []
        for i in range(0,int(verts)):
            inf= cmds.skinPercent(skinClust, (node + ".vtx[" + str(i) + "]"), q=1, v=1)
            activeInf = []
            for j in range(0,len(inf)):
                if inf[j] > 0.0: activeInf.append(inf[j])
            if len(activeInf) > maxInf:
                returnVerts.append(i)
        
        if select:
            for vert in returnVerts:
                cmds.select((node + '.vtx[' + str(vert) + ']'), add=1)
        if debug:
            print 'checkMaxSkinInfluences>>> Total Verts:', verts
            print 'checkMaxSkinInfluences>>> Vertices Over Threshold:', len(returnVerts)
            print 'checkMaxSkinInfluences>>> Indices:', str(returnVerts)
        return returnVerts
    
    def checkLockedInfluences(self, skinCluster):
        '''
        Check if provided skinCluster has locked influences
        '''
        influenceObjects = cmds.skinCluster(skinCluster,q=True, inf=True )
        for currentJoint in influenceObjects:
            if (cmds.skinCluster(skinCluster,q=True,lw=True, inf=currentJoint )):
                return True
        return False
    
    def clampInfFn(self):
        self.clampInfluences(self.currentMesh, self.clampInfSPIN.value(), force=1)
        
    def bindPoseFn(self):
        if self.currentSkin:
            bp = cmds.listConnections(self.currentSkin + '.bindPose', s=1)
            if len(bp) > 0: cmds.dagPose(bp[0], r=1)
            else: cmds.warning('Multiple bind poses detected: ' + str(bp))
        else: cmds.warning('No skin cluster loaded or mesh with skin cluster selected.')
    
    def removeUnusedFn(self):
        if self.currentSkin:
            cmds.skinCluster(self.currentMesh, removeUnusedInfluence=1)
            self.refreshUI()
        else: cmds.warning('No skin cluster loaded or mesh with skin cluster selected.')
    
    def clampInfluences(self, mesh, maxInf, debug=0, force=False):
        '''
        Sets max influences on skincluster of mesh / cutting off smallest ones
        '''
        skinClust = self.findRelatedSkinCluster(mesh)
    
        lockedInfluences = self.checkLockedInfluences(skinClust)
        doit = True
        if lockedInfluences:
            if force:
                self.unlockLockedInfluences(skinClust)
                cmds.warning('Locked influences were unlocked on skinCluster')
            else:
                doit = False
        
        if doit:
            verts = self.checkMaxSkinInfluences(mesh, maxInf)
            
            print 'pruneVertWeights>> Pruning', len(verts), 'vertices'
            
            for v in verts:
                infs = cmds.skinPercent(skinClust, (mesh + ".vtx[" + str(v) + "]"), q=1, v=1)
                active = []
                for inf in infs:
                    if inf > 0.0: active.append(inf)
                active = list(reversed(sorted(active)))
                if debug: print 'Clamping vertex', v, 'to', active[maxInf]
                cmds.skinPercent(skinClust, (mesh + ".vtx[" + str(v) + "]"), pruneWeights=(active[maxInf]*1.001))
        else:
            cmds.warning('Cannot clamp influences due to locked weights on skinCluster')
    
    def addJntFn(self):
        sel = cmds.ls(sl=1)
        if len(sel) == 2:
            mesh, jnt = None, None
            for node in sel:
                if cmds.nodeType(node) == 'joint': jnt = node
                if cmds.listRelatives(node, allDescendents=True, noIntermediate=True, fullPath=True, type="mesh"):
                    mesh = node
            if jnt and mesh:
                cmds.skinCluster(self.findRelatedSkinCluster(mesh), e=1, lw=1, wt=0, ai=jnt)
                cmds.setAttr(jnt + '.liw', 0)
            else:
                cmds.warning('skinWrangler: Cannot find joint and mesh in selection: ' + str(sel))

    ## TOOLS TAB
    ########################################################################
    def makeLocOnSel(self):
        tool = cmds.currentCtx()
        cmds.setToolTo( 'moveSuperContext' )
        pos = cmds.manipMoveContext( 'Move', q=True, p=True )
        startLoc = cmds.spaceLocator (n = ('skinWrangler_jointBboxLocator'))[0]
        cmds.move(pos[0] ,pos[1] ,pos[2] ,startLoc, ws = 1 , a =1)
        cmds.setToolTo(tool)
        return startLoc
    
    def jointOnBboxCenterFn(self):
        if self.jointOnBboxCenterBTN.isChecked() == True:
            self.jointOnBboxCenterBTN.setText('CREATE JOINT FROM ALIGN LOC')
            self.jointLoc = self.makeLocOnSel()
            cmds.setAttr(self.jointLoc + '.displayLocalAxis', 1)
            cmds.select(self.jointLoc)
        else:
            self.jointOnBboxCenterBTN.setText('MAKE JOINT ON BBOX CENTER')
            locXform = cmds.getAttr(self.jointLoc+'.worldMatrix')
            
            #get name
            newName = 'createdJoint'
            inputName, ok = QtGui.QInputDialog.getText(None, 'Creating Node', 'Enter node name:', text=newName)
            if ok: newName = str(inputName)
            cmds.select(cl=1)
            jnt = cmds.joint(name=newName)
            cmds.xform(jnt, m=locXform)
            cmds.delete(self.jointLoc)

    def getPolyShells(self, mesh):
        # returns poly shells as lists of faces
        shells = []
        polygons = [i for i in range(0, cmds.polyEvaluate(f=1))]
        for poly in polygons:
            faces = cmds.polySelect(mesh, ets=poly, q=1)
            shells.append(faces)
            for face in faces:
                polygons.pop(polygons.index(face))
        return shells

    def skinPolyShells(self, mesh, skin):
        # floods each shell with it's avg vtx weight
        try:
            cmds.undoInfo(openChunk=True)
            for shell in self.getPolyShells(mesh):
                facesNice = [mesh + '.f[' + str(f) + ']' for f in shell]
                aw = self.getAvgVertWeights(facesNice, skin)
                tvTuples = self.vDictToTv(aw)
                cmds.skinPercent(skin, facesNice, tv=tvTuples)
        except Exception as e:
            print e
        finally:
            cmds.undoInfo(closeChunk=True)

    def rigidShellsFn(self):
        meshes = cmds.ls(sl=1)
        for mesh in meshes:
            skin = self.findRelatedSkinCluster(mesh)
            self.skinPolyShells(mesh, skin)
    
    ## REFRESH UI
    ###############
    def refreshUI(self):
        refInf = self.currentInf
        self.jointLST.clear()
        self.currentInf = refInf
        
        filter = str(self.filterLINE.text()).lower()
        
        wid = QtWidgets.QTreeWidgetItem()
        font = wid.font(0)
        font.setWeight(QtGui.QFont.Normal)
        font.setPointSize(8)
        
        vertSel = True
        s = self.getSelected()
        if s:
            sel, msh, vtx, skin = s
            self.vtxLBL.setText(str(vtx))
        else:
            wid = QtWidgets.QTreeWidgetItem()
            wid.setText(0, 'MAKE A COMPONENT\n SELECTION ON\n SKINNED MESH')
            wid.setFont(0, font)
            self.jointLST.addTopLevelItem(wid)
            cmds.undoInfo( swf=1)
            self.currentInf = None
            vertSel = False

        skin = None
        if self.currentMesh: self.mshLBL.setText(self.currentMesh)
        if self.currentSkin:
            self.sknLBL.setText(self.currentSkin)
            skin = self.currentSkin
        
        if skin:
            #skin method
            m = cmds.skinCluster(skin, q=1, sm=1)
            if m == 0: self.skinAlgoLBL.setText('Linear')
            if m == 1: self.skinAlgoLBL.setText('DualQuat')
            if m == 2: self.skinAlgoLBL.setText('Blended')
            
            #normalization
            n = cmds.skinCluster(skin, q=1, nw=1)
            if n == 0:
                self.skinNormalCMB.setCurrentIndex(n)
                self.currentNormalization = 'None'
            if n == 1:
                self.skinNormalCMB.setCurrentIndex(n)
                self.currentNormalization = 'Interactive'
            if n == 2:
                self.skinNormalCMB.setCurrentIndex(n)
                self.currentNormalization = 'Post'
            
            #max weights
            self.skinMaxInfLBL.setText(str(cmds.skinCluster(skin, q=1, mi=1)))
            
            if not vertSel: return False
            
            #update jointList
            wDict = self.getAvgVertWeights(sel, skin)
            red = QtGui.QColor(200,75,75,255)
            for inf in wDict.keys():
                if filter in inf.lower() or filter == '':
                    wid = QtWidgets.QTreeWidgetItem()
                    infName = inf
                    if self.nameSpaceCHK.isChecked(): infName = inf.split(':')[-1]
                    wid.setText(0, infName)
                    wid.setForeground(0,red)
                    wid.setForeground(1,red)
                    wid.setIcon(0, self.iconLib['joint'])
                    wid.setText(1, str("%.4f" % wDict[inf]))
                    self.jointLST.addTopLevelItem(wid)
            if self.listAllCHK.isChecked() == True:
                for inf in cmds.skinCluster(self.currentSkin, q=1, inf=1):
                    if inf not in wDict.keys():
                        if filter in inf.lower() or filter == '':
                            wid = QtWidgets.QTreeWidgetItem()
                            wid.setIcon(0, self.iconLib['joint'])
                            if self.nameSpaceCHK.isChecked(): inf = inf.split(':')[-1]
                            wid.setText(0, inf)
                            self.jointLST.addTopLevelItem(wid)
            
            if self.currentInf:
                for item in self.currentInf:
                    self.getJointFromList(item).setSelected(True)
            print 'refreshUI completed.'
                    

    def profileRefreshUI(self):
        import hotshot
        import hotshot.stats
        
        prof = hotshot.Profile("c:\\myFn.prof")
        prof.runcall(self.refreshUI)
        prof.close()
        #now we load the profile stats
        stats = hotshot.stats.load("c:\\myFn.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
         
        #and finally, we print the profile stats to the disk in a file 'myFn.log'
        saveout = sys.stdout
        fsock = open('c:\\myFn.log', 'w')
        sys.stdout = fsock
        stats.print_stats(20)
        sys.stdout = saveout
        fsock.close()

if __name__ == '__main__':
    show()