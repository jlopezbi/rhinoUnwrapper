from visualization import *
import math

class FlatVert():
  def __init__(self,_tVertIdx,_point): 
    self.tVertIdx = _tVertIdx
    self.point = _point
    self.fromFace = None
    #self.toFace = None

    self.edgeIdx = None
    self.geom = []

  def hasSamePoint(self,point):
    return approxEqual(self.point.X,point.X) and approxEqual(self.point.Y,point.Y)

  def translate(self,xForm):
    self.point.Transform(xForm)

class FlatEdge():
  def __init__(self,_edgeIdx,vertI,vertJ): 
    self.edgeIdx = _edgeIdx
    self.I = vertI
    self.J = vertJ
    
    self.line = None
    self.line_id = None
    self.geom = []
    self.type = None
    self.fromFace = None #faces have direct mapping (this is netFace and meshFace)
    self.toFace = None

    '''JOINERY'''
    self.tabOnLeft = None #important for general joinery drawing
    
    '''Tabs'''
    self.hasTab = False
    self.tabFaceCenter = None
    self.tabAngles = []
    self.tabWidth = .2 #could be standard, or based on face area

    '''Holes'''
    self.distI = None
    self.distJ = None

  def reset(self,oldVert,newVert):
    if self.I==oldVert:
      self.I=newVert
    elif self.J==oldVert:
      self.J=newVert
    else:
      assert(False==True), "error, flatEdge does not have oldVert"

  def getCoordinates(self,flatVerts):
    vertI,vertJ = self.getFlatVerts(flatVerts)
    return [vertI.point,vertJ.point]

  def getFlatVerts(self,flatVerts):
    flatVertI = flatVerts[self.I]
    flatVertJ = flatVerts[self.J]
    return (flatVertI,flatVertJ)

  def getNetVerts(self):
    return (self.I,self.J)

  def getTVerts(self,mesh):
    return getTVertsForEdge(mesh,self.edgeIdx)

  '''DRAWING'''

  def drawEdgeLine(self,flatVerts):
    if self.type != None:
      if self.type == 'fold':
        color = (0,49,224,61) #green
      elif self.type == 'cut':
        color = (0,237,43,120) #red
        if self.hasTab:
          color = (0,255,0,255) #magenta
      elif self.type == 'naked':
        color = (0,55,156,196) #blue
      points = self.getCoordinates(flatVerts)
      if self.line_id!=None:
        scriptcontext.doc.Objects.Delete(self.line_id,True)
      line_id,line = drawLine(points,color,'EndArrowhead') #EndArrowhead StartArrowhead
      self.line_id = line_id
      self.line = line
    return line_id

  def getEdgeVec(self,flatVerts):
    pointI = flatVerts[self.I].point
    pointJ = flatVerts[self.J].point
    return Rhino.Geometry.Vector3d(pointJ-pointI)

  def resetFromFace(self,face):
    if self.fromFace==face:
      self.fromFace = self.toFace

  def translateGeom(self,movedNetVerts,flatVerts,xForm):
    #self.translateEdgeLine(xForm)
    self.translateNetVerts(movedNetVerts,flatVerts,xForm)
    if self.tabFaceCenter!=None:
      self.tabFaceCenter.Transform(xForm)

  def translateEdgeLine(self,xForm):
    if self.line != None:
      self.line.Transform(xForm)
      scriptcontext.doc.Objects.Replace(self.line_id,self.line)

  def translateNetVerts(self,movedNetVerts,flatVerts,xForm):
    netVertI,netVertJ = self.getFlatVerts(flatVerts)
    if netVertI not in movedNetVerts:
      netVertI.translate(xForm)
      movedNetVerts.append(netVertI)
    if netVertJ not in movedNetVerts:
      netVertJ.translate(xForm)
      movedNetVerts.append(netVertJ)

  '''JOINERY'''
  def drawTab(self,flatVerts):
    '''outputs guid for polyline'''
    if len(self.geom)>0:
      for guid in self.geom:
        scriptcontext.doc.Objects.Delete(guid,True)
    if len(self.tabAngles)<1:
      return self.drawTriTab(flatVerts)
    else:
      return self.drawQuadTab(flatVerts)
      
  def drawQuadTab(self,flatVerts):
    pntA,pntD = self.getCoordinates(flatVerts)
    vecA = Rhino.Geometry.Vector3d(pntA)
    vecD = Rhino.Geometry.Vector3d(pntD)

    alpha  = self.tabAngles[0]
    beta = self.tabAngles[1]

    lenI = self.tabWidth/math.sin(alpha*math.pi/180.0)
    lenJ = self.tabWidth/math.sin(beta*math.pi/180.0)

    if not self.tabOnLeft:
      alpha = -1*alpha
      beta = -1*beta

    vec = vecD.Subtract(vecD,vecA)
    vecUnit = rs.VectorUnitize(vec)
    vecI = rs.VectorScale(vecUnit,lenI)
    vecJ = rs.VectorScale(vecUnit,-lenJ)

    vecI = rs.VectorRotate(vecI,alpha,[0,0,1]) 
    vecJ = rs.VectorRotate(vecJ,-beta,[0,0,1])
    vecB = vecA + vecI
    vecC = vecD + vecJ

    pntB = Rhino.Geometry.Point3d(vecB)
    pntC = Rhino.Geometry.Point3d(vecC)

    points = [pntA,pntB,pntC,pntD]
    polyGuid = rs.AddPolyline(points)

    self.geom.append(polyGuid)
    return polyGuid

  def drawTriTab(self,flatVerts):
    pntA,pntC = self.getCoordinates(flatVerts)
    pntB = self.tabFaceCenter

    points = [pntA,pntB,pntC]
    polyGuid = rs.AddPolyline(points)
    self.geom.append(polyGuid)
    return polyGuid

  def drawHoles(self,flatFaces):
    pass

  def assignHoleDistances(self,net):
    if self.distI==None and self.distJ==None:
      pair = net.flatEdges[self.pair]
      distsA = pair.getHoleDistances(net)
      distsB = self.getHoleDistances(net)
      distI = max(distsA[0],distsB[0])
      distJ = max(distsA[1],distsB[1])
      
      pair.distI = distI
      pair.distJ = distJ
      self.distI = distI
      self.distJ = distJ

  def getHoleDistances(self,net):
    axis = Rhino.Geometry.Vector3d(0.0,0.0,1.0) #assumes laying-out in xy plane
    point = self.getFacePoint(net.flatVerts,net.flatFaces)
    edgeOffset = self.offset(edgeVec,point)

  def getOffsetLine(self,flatVerts,facePoint,axis,distance):
    '''return a line which is offset from the edge by the distance specified
    the line is on the inside of the face 
    '''
    edgeVec = self.getEdgeVec(flatVerts)
    edgeVecChange = Rhino.Geometry.Vector3d(edgeVec) 
    edgeVecChange.Unitize()
    tabOnLeft = self.setTabSide(facePoint,flatVerts)
    if tabOnLeft:
      edgeVecChange.Rotate(-math.pi/2.0,axis)
    else:
      edgeVecChange.Rotate(math.pi/2.0,axis)
    offsetVec = Rhino.Geometry.Vector3d.Multiply(edgeVecChange,distance)
    offsetPoint = Rhino.Geometry.Point3d(offsetVec)
    point = offsetPoint+flatVerts[self.I].point
    return Rhino.Geometry.Line(point,edgeVec)


  def getFacePoint(self,flatVerts,flatFaces):
    return flatFaces[self.fromFace].getCenterPoint(flatVerts)

  def clearAllGeom(self):
    '''
    note: clear self.geom and self.line_id ?
    '''
    if self.line_id !=None:
      scriptcontext.doc.Objects.Delete(self.line_id,True)
      self.line_id = None

    if len(self.geom)>0:
      for guid in self.geom:
        scriptcontext.doc.Objects.Delete(guid,True)
  
  def getMidPoint(self,flatVerts):
    coordinates = self.getCoordinates(flatVerts)
    pntA = coordinates[0]
    pntB = coordinates[1]
    x = (pntA.X+pntB.X)/2.0
    y = (pntA.Y+pntB.Y)/2.0
    z = (pntA.Z+pntB.Z)/2.0
    return Rhino.Geometry.Point3f(x,y,z)

  def getFaceFromPoint(self,net,point):
    '''return the face that corresponds to the point
    '''
    #TODO: fails for horizontal lines :(
    assert(self.type =='fold')
    faceA = self.fromFace
    faceB = self.toFace
    leftA = self.testFacesIsLeft(net,faceA)
    leftB = self.testFacesIsLeft(net,faceB)
    assert(leftA!=leftB),"both faces found to be on same side of edge"
    leftPoint = self.testPointIsLeft(point,net.flatVerts)
    if leftA==leftPoint:
      return faceA
    elif leftB==leftPoint:
      return faceB
    print "unable to find face"
    return 

  def testFacesIsLeft(self,net,face):
    '''find which side the face is on relative to this edge
    ouput: 1 for left, -1 for right, 0 for error
    '''

    testPoint = net.flatVerts[self.getNeighborFlatVert(net,face)].point
    if not testPoint:
      return -1
    return self.testPointIsLeft(testPoint,net.flatVerts)
  
  def setTabSide(self,facePoint,flatVerts):
    '''
    occurs affter complete layout
    '''
    if self.tabOnLeft == None:
      #testPoint = net.flatVerts[self.getNeighborFlatVert(net)].point
      if self.testPointIsLeft(facePoint,flatVerts):
        self.tabOnLeft = False
      else:
        self.tabOnLeft = True
      return self.tabOnLeft
    else:
      return self.tabOnLeft

  def testPointIsLeft(self,testPoint,flatVerts):
    '''
    use cross product to see if testPoint is to the left of 
    the edgLine
    returns False if co-linear. HOwever, if the mesh is triangulated
    and has no zero-area faces this should not occur.
    '''
    pntA,pntB = self.getCoordinates(flatVerts)
    vecLine = getVectorForPoints(pntA,pntB)
    vecTest = getVectorForPoints(pntA,testPoint)#this may be too skewed
    cross = Rhino.Geometry.Vector3d.CrossProduct(vecLine,vecTest)
    z = cross.Z #(pos and neg)
    return  z > 0 

  def getNeighborFlatVert(self,net,face=None):
    '''
    gets one of the flatVerts associated with the given
    face, but that is not a part of this flatEdge.
    if face==None uses the fromFace associated with this edge
    '''

    if face==None:
      face = self.fromFace
    tVertsEdge = set([self.I,self.J])
    flatFace = net.flatFaces[face]
    tVertsFace = set(flatFace.vertices)
    neighbors = list(tVertsFace-tVertsEdge)
    return neighbors[0] #arbitrarily return first tVert

  def getTabFaceCenter(self,mesh,currFace,xForm):
    otherFace = getOtherFaceIdx(self.edgeIdx,currFace,mesh)
    if otherFace!=None:
      faceCenter = mesh.Faces.GetFaceCenter(otherFace)
      faceCenter.Transform(xForm)
      self.tabFaceCenter = faceCenter
    if self.tabFaceCenter==None:
      return False
    else:
      return True

  def getTabAngles(self,mesh,currFaceIdx,xForm):
    #WORKING AWAY FROM THIS: data is implicit in tabFaceCenter
    edge = self.edgeIdx
    otherFace = getOtherFaceIdx(edge,currFaceIdx,mesh)

    if otherFace != None:
      faceCenter = mesh.Faces.GetFaceCenter(otherFace) #Point3d
      if getDistanceToEdge(mesh,edge,faceCenter)<=self.tabWidth:
        faceCenter.Transform(xForm)
        self.tabFaceCenter = faceCenter
      else:
        posVecCenter = Rhino.Geometry.Vector3d(faceCenter) 

        pntI,pntJ = getPointsForEdge(mesh,edge) #Point3d
        vecEdge = getEdgeVector(mesh,edge) #Vector3d
        posVecI = Rhino.Geometry.Vector3d(pntI)
        posVecJ = Rhino.Geometry.Vector3d(pntJ)

        vecI = Rhino.Geometry.Vector3d.Subtract(posVecCenter,posVecI)
        vecJ = Rhino.Geometry.Vector3d.Subtract(posVecJ,posVecCenter)
        
        angleI = rs.VectorAngle(vecI,vecEdge)
        angleJ = rs.VectorAngle(vecJ,vecEdge)

        self.tabAngles = [angleI,angleJ]

        """
        color = (0,0,0,0)
        drawVector(vecI,posVecI,color)
        drawVector(vecJ,posVecCenter,color)
        strI = str(angleI)
        strJ = str(angleJ)
        rs.AddTextDot(strI,posVecI)
        rs.AddTextDot(strJ,posVecJ)
        print #wtf: for some reason needed this line to print below
        print( 'angleI: %.2f, angleJ: %.2f' %(angleI,angleJ) )
        """
    elif otherFace==-1:
      print "was nakedEdge"
    else:
      print "otherFace: ",
      print otherFace


class FlatFace():
  #does not store meshFace because position in list determines this
  def __init__(self,_vertices,_fromFace):
    self.vertices = _vertices # a list of netVerts
    self.fromFace = _fromFace
    self.centerPoint = None

  def getFlatVerts(self,flatVerts):
    collection = []
    for vert in self.vertices:
      collection.append(flatVerts[vert])
    return collection

  def getFlatVertForTVert(self,tVert,flatVerts):
    assert(tVert in self.vertices.keys())
    return flatVerts[tVert][self.vertices[tVert]]

  def getCenterPoint(self,flatVerts):
    if self.centerPoint==None:
      flatVerts = self.getFlatVerts(flatVerts)
      nVerts = len(self.vertices)
      sumX = 0.0
      sumY = 0.0
      for flatVert in flatVerts:
        point = flatVert.point
        sumX += point.X
        sumY += point.Y
      x = sumX/nVerts
      y = sumY/nVerts
      self.centerPoint = Rhino.Geometry.Point3d(x,y,0.0)
    return self.centerPoint

  def draw(self,flatVerts):
    points = [flatVerts[i].point for i in self.vertices]
    #add first vert to end to make closed
    points.append(flatVerts[self.vertices[0]].point) 
    #remove 'EndArrowhead' to stop displaying orientatio of face
    poly_id,polyline = drawPolyline(points,[0,0,0,0],'EndArrowhead')
    self.poly_id = poly_id
    self.polyline = polyline

  def drawInnerface(self,flatVerts,ratio=.33):
    '''draw a inset face'''
    self.getCenterPoint(flatVerts)
    centerVec = Rhino.Geometry.Vector3d(self.centerPoint)
    for i in range(len(self.vertices)):
      vert = self.vertices[i]
      self.getInnerPoint(flatVerts,vert)
      #TODO: finish up this function

  def getInnerPoint(self,flatVerts,vert):
    cornerVec = Rhino.Geometry.Vector3d(flatVerts[vert].point)
    vec = Rhino.Geometry.Vector3d(centerVec-cornerVec)
    length = vec.Length
    if not vec.Unitize(): return
    vec = vec.Multiply(vec,length*ratio)
    pos = Rhino.Geometry.Vector3d.Add(cornerVec,vec)
    rs.AddTextDot(str(i),pos)








  
