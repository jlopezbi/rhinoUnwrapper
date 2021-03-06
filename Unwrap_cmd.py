import rhino_unwrapper.unfold as unfold
import rhino_unwrapper.rhino_inputs as ri
import rhino_unwrapper.weight_functions as wf
import rhino_unwrapper.mesh as m
import rhino_unwrapper.Map as mapper
import inspect

reload(unfold)
reload(ri)
reload(wf)
reload(m)
reload(mapper)


def all_weight_functions():
    return dict([m for m in inspect.getmembers(wf, inspect.isfunction)])


__commandname__ = "Unwrap"

def RunCommand():
    holeRadius = 0.125/2.0
    mesh = ri.getMesh("Select mesh to unwrap")
    if not mesh: return
    print "got a mesh: ",
    print mesh
    myMesh = m.Mesh(mesh)

    userCuts = ri.getUserCuts(myMesh)
    if userCuts == None: return

    print all_weight_functions()
    weightFunction = ri.getOptions_dict(all_weight_functions())
    island_creator  = unfold.IslandCreator(mapper.Map(myMesh),fold_list,myMesh)

    if mesh and weightFunction:
        unfolder = unfold.UnFolder()
        dataMap,net = unfolder.unfold(myMesh,userCuts,weightFunction,holeRadius)
        net.findInitalSegments() 
        net.draw_edges() 

        while True:
            flatEdge,idx = ri.get_new_cut("select new edge on net or mesh",net,dataMap)
            # TODO: figure out how to check type or isinstance of flatEdge -> cut
            # or fold. Maybe avoid this completely by duck typing?
            # would be something like flatEdge.process_selection.
            # flatEdge.process_cut_selection. oof. or maybe that is something
            # that the net should handle. that sounds better. temporary fix for
            # now
            if flatEdge.type() == 'FoldEdge':
                basePoint = flatEdge.getMidPoint(net.flatVerts)
                xForm,point = ri.getUserTranslate("Pick point to translate segment to",basePoint)
                if xForm and point:
                    face = flatEdge.getFaceFromPoint(net.flatFaces,net.flatVerts,point)
                    segment = net.findSegment(flatEdge,face)
                    net.copyAndReasign(dataMap,flatEdge,idx,segment,face)
                    translatedEdges = net.translateSegment(segment,xForm)
                    net.redrawSegment(translatedEdges)
            elif flatEdge.type() == 'CutEdge':
                pass
            elif flatEdge == None:
                break

if __name__=="__main__":
    RunCommand()
