#THIS_PROJECT STUFF
import transformations as trans
import flatEdge as fe
import flatGeom
import Net as nt
import island
import traversal as tr
import Map
import rhino_inputs as ri
import weight_functions as wf

#RHINO STUFF
import rhinoscriptsyntax as rs
import Rhino

#PYTHON STUFF
import collections,inspect

reload(flatGeom)
reload(trans)
reload(fe)
reload(nt)
reload(island)
reload(tr)

MeshLoc = collections.namedtuple('MeshLoc',['face','edge'])
IslandLoc = collections.namedtuple('IslandLoc',['face','edge']) #note face for island loc is prevFace

class IslandMaker(object):

    def __init__(self,dataMap,myMesh,island_index=0):
        '''
        creates and island, which is a special mesh for representing an unfolded section of a mesh
        '''
        self.dataMap = dataMap
        self.myMesh = myMesh
        #island_index may eventaully be useful for grouping the island for fast island identification
        self.island_index = island_index #index of island in net
        self.visualize_mode = False
        self.visited_faces = []
        self.visited_edges = []

    def make_island(self,meshLoc=None,startFrame=trans.make_origin_frame()):
        self.island = island.Island()
        self.island.add_dummy_elements()
        assert self.myMesh.get_cuts(), "cuts not set!"
        if meshLoc==None:
            meshLoc = MeshLoc(0,0)
        startIslandLoc = IslandLoc(face=0,edge=0)
        self.layout_first_two_points(meshLoc,startFrame)
        self.breadth_first_layout(self.island,meshLoc,startIslandLoc)
        self.island.reverse_order_dummy_face()
        return self.island,self.visited_faces
    
    def spawn_island(self):
        self.island = island.Island()
        self.island.add_dummy_elements()

    def make_island_no_cuts(self,meshLoc=None,startFrame=trans.make_origin_frame()):
        '''
        Does not use cut list; unfolds until all faces have been touched
        '''
        self.spawn_island() 
        if meshLoc==None:
            meshLoc = MeshLoc(0,0)
        startIslandLoc = IslandLoc(face=0,edge=0)
        self.layout_first_two_points(meshLoc,startFrame)
        self.breadth_first_layout_face_version(self.island,meshLoc,startIslandLoc)
        return self.island

    def layout_first_two_points(self,meshLoc,start_frame):
        '''
        The process must be started with an island that has one edge, its from face, and the two verts
        for that face and edge. This function adds those verts
        Note that the verts are added in reverse order; this is consistent with the assumption
        of breadth_first_layout.
        '''
        meshPointA,meshPointB = self.myMesh.get_oriented_points_for_edge(meshLoc.edge,meshLoc.face)
        self.visited_edges.append(meshLoc.edge)
        from_frame = self.myMesh.get_frame_oriented_with_face_normal(meshLoc.edge,meshLoc.face)
        pnt0 = trans.get_mapped_point(meshPointA,from_frame,start_frame)
        pnt1 = trans.get_mapped_point(meshPointB,from_frame,start_frame)
        self.island.add_vert_from_point(pnt1)
        self.island.add_vert_from_point(pnt0)
        meshEdge = meshLoc.edge
        islandEdge = 0
        #NOTE: only works for myMeshes that have cuts set! consider alternatives to deal with this
        if self.myMesh.is_fold_edge(meshEdge):
            self.island.change_to_fold_edge(islandEdge)
        if self.myMesh.is_cut_edge(meshEdge):
            self.island.change_to_cut_edge(islandEdge)
        if self.myMesh.is_naked_edge(meshEdge):
            self.island.change_to_naked_edge(islandEdge)
            
    def breadth_first_layout(self,island,startMeshLoc,startIslandLoc):
        ''' for layout to not accidently infinite loop the startMeshLoc must be on cut or naked edge
        '''
        assert (self.myMesh.is_cut_edge(startMeshLoc.edge) or self.myMesh.is_naked_edge(startMeshLoc.edge)),  "meshloc is not on a cut edge or a naked edge!"
        layoutPair = (startMeshLoc,startIslandLoc)
        queue = collections.deque([layoutPair])
        self.visited_faces.append(startMeshLoc.face)
        while True:
            try:
                meshLoc,islandLoc = queue.popleft()
            except IndexError:
                break
            orientedEdges = self.myMesh.get_edges_ccw_besides_base(meshLoc.edge,meshLoc.face) 
            newVerts = []
            newEdges = []
            islandFaceToBe = island.next_face_index()
            for i,orientedEdge in enumerate(orientedEdges):
                edge,alignedWithFace = orientedEdge
                face = self.myMesh.getOtherFaceIdx(edge,meshLoc.face)
                # the last edge's head has already been layed out
                if orientedEdge != orientedEdges[-1]: 
                    tailPoint,headPoint = self.myMesh.get_aligned_points(orientedEdge) 
                    mapped_point = self.get_mapped_point(headPoint,meshLoc,islandLoc) 
                    island.layout_add_vert_point(mapped_point) 
                angle = self.myMesh.getEdgeAngle(edge)
                newEdge = island.layout_add_edge(i+1,edge,angle)
                if self.myMesh.is_fold_edge(edge):
                    island.change_to_fold_edge(edge=newEdge)
                    self.visited_faces.append(face)
                    island.update_edge_to_face(edge=newEdge,toFace=islandFaceToBe+(i+1)) 
                    newMeshLoc = MeshLoc(face,edge)
                    newIslandLoc = IslandLoc(islandFaceToBe,newEdge)
                    queue.append((newMeshLoc,newIslandLoc))
                elif self.myMesh.is_cut_edge(edge): 
                    is_first = True
                    if edge in self.visited_edges:
                        is_first = False
                    island.change_to_cut_edge(edge=newEdge,isLeader=is_first)
                elif self.myMesh.is_naked_edge(edge): 
                    island.change_to_naked_edge(edge=newEdge) 
                self.visited_edges.append(edge)
            island.layout_add_face(baseEdge=islandLoc.edge)

    def breadth_first_layout_face_version(self,island,startMeshLoc,startIslandLoc):
        '''
        traverse all faces of mesh breadth first and create an island
        (does not check if edges are cut or fold) 
        need to figure out how to setup island so ready to do this function...
        '''
        layoutPair = (startMeshLoc,startIslandLoc)
        queue = collections.deque([layoutPair])
        visited = [startMeshLoc.face]
        while True:
            try:
                meshLoc,islandLoc = queue.popleft()
            except IndexError:
                break
            orientedEdges = self.myMesh.get_edges_ccw_besides_base(meshLoc.edge,meshLoc.face) 
            newVerts = []
            newEdges = []
            islandFaceToBe = island.next_face_index()
            for i,orientedEdge in enumerate(orientedEdges):
                edge,alignedWithFace = orientedEdge
                face = self.myMesh.getOtherFaceIdx(edge,meshLoc.face)
                if orientedEdge != orientedEdges[-1]: # the last edge's head has already been layed out
                    tailPoint,headPoint = self.myMesh.get_aligned_points(orientedEdge) 
                    mapped_point = self.get_mapped_point(headPoint,meshLoc,islandLoc) 
                    island.layout_add_vert_point(mapped_point) 
                newEdge = island.layout_add_edge(i+1)
                if face and face not in visited:
                    visited.append(face)
                    island.update_edge_to_face(edge=newEdge,toFace=islandFaceToBe+(i+1)) 
                    newMeshLoc = MeshLoc(face,edge)
                    newIslandLoc = IslandLoc(islandFaceToBe,newEdge)
                    queue.append((newMeshLoc,newIslandLoc))
            island.layout_add_face(baseEdge=islandLoc.edge)

    def get_mapped_point(self,point,meshLoc,islandLoc):
        from_frame = self.myMesh.get_frame_oriented_with_face_normal(meshLoc.edge,meshLoc.face)
        to_frame = self.island.get_frame_reverse_edge(islandLoc.edge,islandLoc.face)
        if self.visualize_mode:
            from_frame.show()
            to_frame.show()
        return  trans.get_mapped_point(point,from_frame,to_frame)
    
def breadth_first_traverse(myMesh,face):
    '''
    practice function for traversing mesh breadth-first
    '''
    queue = collections.deque([face])
    visited = [face]
    while True:
        try:
            nextFace = queue.popleft()
            #nextMeshLoc = queue.popleft()
            #Add face to Island(face,meshloc,islandloc)
        except IndexError:
            break
        for neighbor in myMesh.get_adjacent_faces(nextFace):
            if neighbor not in visited:
                visited.append(neighbor)
                queue.append(neighbor)
    return visited
