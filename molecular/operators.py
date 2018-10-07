
from time import clock, sleep, strftime, gmtime

import bpy
from mathutils import Vector
from mathutils.geometry import barycentric_transform as barycentric

from . import simulate

try:
    from . import cmolcore
except:
    print("cmolcore not working")


class MolSimulate(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.mol_simulate"
    bl_label = "Mol Simulate"

    def execute(self, context):
        print("Molecular Sim start--------------------------------------------------")
        mol_stime = clock()
        scene = bpy.context.scene
        scene.mol_simrun = True
        scene.mol_minsize = 1000000000.0
        scene.mol_newlink = 0
        scene.mol_deadlink = 0
        scene.mol_totallink = 0
        scene.mol_totaldeadlink = 0
        scene.mol_timeremain = "...Simulating..."
        object = bpy.context.object
        scene.frame_set(frame=scene.frame_start)
        scene.mol_old_endframe = scene.frame_end
        mol_substep = scene.mol_substep
        scene.render.frame_map_old = 1
        scene.render.frame_map_new = mol_substep + 1
        scene.frame_end *= mol_substep + 1

        if scene.mol_timescale_active == True:
            fps = scene.render.fps / scene.timescale
        else:
            fps = scene.render.fps

        cpu = scene.mol_cpu
        mol_exportdata = bpy.context.scene.mol_exportdata
        mol_exportdata.clear()
        mol_exportdata.append([fps, mol_substep, 0, 0, cpu])
        mol_stime = clock()
        simulate.pack_data(True)
        #print("sys number",mol_exportdata[0][2])
        etime = clock()
        print("  PackData take " + str(round(etime - mol_stime, 3)) + "sec")
        mol_stime = clock()
        mol_report = cmolcore.init(mol_exportdata)
        etime = clock()
        print("  Export time take " + str(round(etime - mol_stime, 3)) + "sec")
        print("  total numbers of particles: " + str(mol_report))
        print("  start processing:")
        bpy.ops.wm.mol_simulate_modal()
        return {'FINISHED'}


class MolSetGlobalUV(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.mol_set_global_uv"
    bl_label = "Mol Set UV"

    def execute(self, context):
        scene = bpy.context.scene
        object = bpy.context.object
        psys = object.particle_systems.active
        coord = [0, 0, 0] * len(psys.particles)
        psys.particles.foreach_get("location", coord)
        psys.particles.foreach_set("angular_velocity", coord)

        return {'FINISHED'}


class MolSetActiveUV(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.mol_set_active_uv"
    bl_label = "Mol Set Active UV"

    def execute(self, context):
        scene = context.scene
        scene.mol_objuvbake = context.object.name
        scene.mol_psysuvbake = context.object.particle_systems.active.name
        object = bpy.data.objects[scene.mol_objuvbake]

        if not object.data.uv_layers.active:
            return {'FINISHED'}

        print('  start bake uv from:',object.name)
        #object2 = object.copy()

        obdata = object.data.copy()
        object2 = bpy.data.objects.new(name="mol_uv_temp", object_data=obdata)
        object2.matrix_world = object.matrix_world

        context.scene.objects.link(object2)
        mod = object2.modifiers.new("tri_for_uv", "TRIANGULATE")
        mod.ngon_method = 'BEAUTY'
        mod.quad_method = 'BEAUTY'
        newmesh = object2.to_mesh(bpy.context.scene, True, "RENDER", True, False)
        object2.data = newmesh
        context.scene.update()
        """
        oldmesh = object.data
        newmesh = object.data.copy()
        object.data = newmesh
        mod = object.modifiers.new("tri_for_uv","TRIANGULATE")
        mod.use_beauty = False
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier=mod.name)
        """
        psys = context.object.particle_systems[scene.mol_psysuvbake]
        #print('-------------start------------')
        for par in psys.particles:
            parloc = (par.location * object2.matrix_world) - object2.location
            point = object2.closest_point_on_mesh(parloc)
            #print('closest:',par.location,point[0],point[2])
            vindex1 = object2.data.polygons[point[3]].vertices[0]
            vindex2 = object2.data.polygons[point[3]].vertices[1]
            vindex3 = object2.data.polygons[point[3]].vertices[2]
            v1 = (object2.matrix_world * object2.data.vertices[vindex1].co).to_tuple()
            v2 = (object2.matrix_world * object2.data.vertices[vindex2].co).to_tuple()
            v3 = (object2.matrix_world * object2.data.vertices[vindex3].co).to_tuple()
            uvindex1 = object2.data.polygons[point[3]].loop_start + 0
            uvindex2 = object2.data.polygons[point[3]].loop_start + 1
            uvindex3 = object2.data.polygons[point[3]].loop_start + 2
            uv1 = object2.data.uv_layers.active.data[uvindex1].uv.to_3d()
            uv2 = object2.data.uv_layers.active.data[uvindex2].uv.to_3d()
            uv3 = object2.data.uv_layers.active.data[uvindex3].uv.to_3d()
            #print(vertices1.co,vertices2.co,vertices3.co)
            #print(uv1,uv2,uv3)
            p = object2.matrix_world * point[1]
            v1 = Vector(v1)
            v2 = Vector(v2)
            v3 = Vector(v3)
            uv1 = Vector(uv1)
            uv2 = Vector(uv2)
            uv3 = Vector(uv3)
            #print(a,b,c,uv1,uv2,uv3,p)
            newuv = barycentric(p,v1,v2,v3,uv1,uv2,uv3)
            #print('New UVs:',newuv)
            parloc = par.location * object2.matrix_world
            dist = (Vector((parloc[0] - p[0], parloc[1] - p[1], parloc[2] - p[2]))).length
            newuv[2] = dist
            newuv = newuv.to_tuple()
            par.angular_velocity = newuv
        scene.objects.unlink(object2)
        bpy.data.objects.remove(object2)
        bpy.data.meshes.remove(newmesh)
        print('         uv baked on:',psys.settings.name)

        return {'FINISHED'}


class MolSimulateModal(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = "wm.mol_simulate_modal"
    bl_label = "Simulate Molecular"
    _timer = None

    def modal(self, context, event):
        #mol_stime = clock()
        scene = bpy.context.scene
        frame_end = scene.frame_end
        frame_current = scene.frame_current
        if event.type == 'ESC' or frame_current == frame_end:
            if frame_current == frame_end and scene.mol_bake == True:
                fake_context = bpy.context.copy()
                for obj in bpy.data.objects:
                    for psys in obj.particle_systems:
                        if psys.settings.mol_active == True  and len(psys.particles) > 0:
                            fake_context["point_cache"] = psys.point_cache
                            bpy.ops.ptcache.bake_from_cache(fake_context)
            scene.render.frame_map_new = 1
            scene.frame_end = scene.mol_old_endframe

            for obj in bpy.data.objects:
                for psys in obj.particle_systems:
                    for psys in obj.particle_systems:
                        if psys.settings.mol_bakeuv == True:
                            scene.mol_objuvbake = obj.name
                            mol_psysuvbake = psys.name
                            bpy.context.scene.update()
                            scene.frame_set(frame = psys.settings.frame_start)
                            bpy.context.scene.update()
                            bpy.ops.object.mol_set_active_uv()

            if frame_current == frame_end and scene.mol_render == True:
                bpy.ops.render.render(animation=True)

            scene.frame_set(frame = scene.frame_start)

            cmolcore.memfree()
            scene.mol_simrun = False
            mol_exportdata = scene.mol_exportdata
            mol_exportdata.clear()
            print("--------------------------------------------------Molecular Sim end")
            return self.cancel(context)

        if event.type == 'TIMER':
            if frame_current == scene.frame_start:            
                scene.mol_stime = clock()
            mol_exportdata = bpy.context.scene.mol_exportdata
            mol_exportdata.clear()
            #stimex = clock()
            simulate.pack_data(False)
            #print("packdata time",clock() - stimex,"sec")
            mol_importdata = cmolcore.simulate(mol_exportdata)
            i = 0
            #stimex = clock()
            for obj in bpy.data.objects:
                for psys in obj.particle_systems:
                    if psys.settings.mol_active == True  and len(psys.particles) > 0:
                        #print(len(mol_importdata[i][1]))
                        #print(len(psys.particles))
                        psys.particles.foreach_set('velocity',mol_importdata[1][i])
                        i += 1
            #print("inject new velocity time",clock() - stimex,"sec")
            mol_substep = scene.mol_substep
            framesubstep = frame_current/(mol_substep + 1)        
            if framesubstep == int(framesubstep):
                etime = clock()
                print("    frame " + str(framesubstep + 1) + ":")
                print("      links created:", scene.mol_newlink)
                if scene.mol_totallink != 0:
                    print("      links broked :", scene.mol_deadlink)
                    print("      total links:", scene.mol_totallink - scene.mol_totaldeadlink ,"/", scene.mol_totallink," (",round((((scene.mol_totallink - scene.mol_totaldeadlink) / scene.mol_totallink) * 100), 2), "%)")
                print("      Molecular Script: " + str(round(etime - scene.mol_stime, 3)) + " sec")
                remain = (((etime - scene.mol_stime) * (scene.mol_old_endframe - framesubstep - 1)))
                days = int(strftime('%d', gmtime(remain))) - 1
                scene.mol_timeremain = strftime(str(days) + ' days %H hours %M mins %S secs', gmtime(remain))
                print("      Remaining estimated:", scene.mol_timeremain)
                scene.mol_newlink = 0
                scene.mol_deadlink = 0
                scene.mol_stime = clock()
                stime2 = clock()
            scene.mol_newlink += mol_importdata[2]
            scene.mol_deadlink += mol_importdata[3]
            scene.mol_totallink = mol_importdata[4]
            scene.mol_totaldeadlink = mol_importdata[5]
            scene.frame_set(frame = frame_current + 1)
            if framesubstep == int(framesubstep):
                etime2 = clock()
                print("      Blender: " + str(round(etime2 - stime2, 3)) + " sec")
                stime2 = clock()
        return {'PASS_THROUGH'}

    def execute(self, context):
        self._timer = context.window_manager.event_timer_add(0.000000001, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        return {'CANCELLED'}   
