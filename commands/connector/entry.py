# connector
import math
import adsk.core
import adsk.fusion
import os
from copy import deepcopy
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface
design = app.activeProduct
rootComp = design.rootComponent
newOccu = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
newComp = newOccu.component

CMD_NAME = os.path.basename(os.path.dirname(__file__))
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = 'Creates a body connecting dowel treads'
IS_PROMOTED = True

# Global variables by referencing values from /config.py
WORKSPACE_ID = config.design_workspace
TAB_ID = config.tools_tab_id
TAB_NAME = config.my_tab_name

PANEL_ID = config.my_panel_id
PANEL_NAME = config.my_panel_name
PANEL_AFTER = config.my_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Holds references to event handlers
local_handlers = []


# Executed when add-in is run.
def start():
    # ******************************** Create Command Definition ********************************
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Add command created handler. The function passed here will be executed when the command is executed.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******************************** Create Command Control ********************************
    # Get target workspace for the command.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get target toolbar tab for the command and create the tab if necessary.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    # Get target panel for the command and and create the panel if necessary.
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    # Create the command control, i.e. a button in the UI.
    control = panel.controls.addCommand(cmd_def)

    # Now you can set various options on the control such as promoting it to always be shown.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    # Delete the panel if it is empty
    if panel.controls.count == 0:
        panel.deleteMe()

    # Delete the tab if it is empty
    if toolbar_tab.toolbarPanels.count == 0:
        toolbar_tab.deleteMe()



# Function to be called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute_intersection, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    button_icons = os.path.join(ICON_FOLDER, 'buttons')
    inputs = args.command.commandInputs

    origin_point = adsk.core.Point3D.create(0, 0, 0)
    x_vector = adsk.core.Vector3D.create(1, 0, 0)
    y_vector = adsk.core.Vector3D.create(0, 1, 0)
    z_vector = adsk.core.Vector3D.create(0, 0, 1)

    # Selection input for multiple circular edges
    selection_input = inputs.addSelectionInput('selection_input', 'Select Circular Edges', 'Select multiple circular edges')
    selection_input.addSelectionFilter('CircularEdges')
    selection_input.setSelectionLimits(2, 0)  # Minimum 2 selections, no maximum


def command_execute_intersection(args: adsk.core.CommandEventArgs):
    futil.log('Find Intersection Command Execute Event')
    inputs = args.command.commandInputs

    # Get the selection input
    selection_input = inputs.itemById('selection_input')

    # Lists to store the lines (points and direction vectors)
    points = []
    directions = []

    # Store circle geometries for later use
    circle_geometries = []

    # Iterate over the selected edges
    for i in range(selection_input.selectionCount):
        selected_edge = selection_input.selection(i).entity

        # Check if the selected entity is a BRepEdge
        if isinstance(selected_edge, adsk.fusion.BRepEdge):
            edge_geometry = selected_edge.geometry
            

            # Check if the edge geometry is a Circle3D
            if isinstance(edge_geometry, adsk.core.Circle3D):
                # Check all faces associated with the edge
                edge_faces = selected_edge.faces

                #Check for planar face
                for j in range(edge_faces.count):
                    edge_face = edge_faces.item(j)
                    face_eval = edge_face.geometry.surfaceType
                    futil.log(f'Selection {i} face {j} surfaceType: {face_eval}')
                    if (face_eval == 0):
                        circle_face = edge_face
                        break
                
                face_geometries = circle_face.geometry
                center_point = edge_geometry.center
                normal_vector = face_geometries.normal
                radius = edge_geometry.radius
                futil.log(f'Center point: {center_point}, normal: {normal_vector}, radius: {radius}')
                # Store the point and direction
                points.append(center_point)
                directions.append(normal_vector)

                # Store circle geometry for tube creation
                circle_geometries.append({
                    'center_point': center_point,
                    'normal_vector': normal_vector,
                    'radius': radius
                })

            else:
                ui.messageBox(f'Selected edge {i+1} is not a circle.')
                return
        else:
            ui.messageBox(f'Selected entity {i+1} is not an edge.')
            return

    # Compute the intersection point
    intersection_point = compute_best_intersection(points, directions)

    if intersection_point:
        baseFeat = None
        if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            baseFeat = rootComp.features.baseFeatures.add()
            baseFeat.startEdit()

        # Create a construction point at the intersection
        points_collection = rootComp.constructionPoints
        pointInput = points_collection.createInput()
        pointInput.setByPoint(intersection_point)
        points_collection.add(pointInput)

        for geom in circle_geometries:
            create_tube(geom, intersection_point, baseFeat)

        if baseFeat:
            baseFeat.finishEdit()

        # Display the point coordinates
        x = intersection_point.x
        y = intersection_point.y
        z = intersection_point.z
        ui.messageBox(f'Intersection Point:\nX: {x:.4f}\nY: {y:.4f}\nZ: {z:.4f}')
    else:
        ui.messageBox('Could not find an intersection point.')

def compute_best_intersection(points, directions):
    """
    Computes the point that minimizes the sum of squared distances to all lines defined by points and directions.

    Args:
        points (list of adsk.core.Point3D): Points through which the lines pass.
        directions (list of adsk.core.Vector3D): Direction vectors of the lines.

    Returns:
        adsk.core.Point3D: The point closest to all lines, or None if computation fails.
    """
    n = len(points)
    if n < 2:
        return None

    # Initialize matrices
    S = [[0.0]*3 for _ in range(3)]
    C = [0.0]*3

    for i in range(n):
        p = points[i]
        d = directions[i]
        d.normalize()  # Ensure the direction vector is a unit vector

        # Extract components
        dx, dy, dz = d.x, d.y, d.z
        px, py, pz = p.x, p.y, p.z

        d_array = [dx, dy, dz]
        p_array = [px, py, pz]

        # Build the projection matrix M = I - d d^T
        M = [[0.0]*3 for _ in range(3)]
        for j in range(3):
            for k in range(3):
                M[j][k] = - d_array[j] * d_array[k]
                if j == k:
                    M[j][k] += 1.0  # Add 1 to diagonal elements

        # Accumulate S and C
        for j in range(3):
            for k in range(3):
                S[j][k] += M[j][k]

        for j in range(3):
            C[j] += sum(M[j][k] * p_array[k] for k in range(3))

    # Solve the linear system S * x = C
    try:
        x = solve_linear_system(S, C)
        intersection_point = adsk.core.Point3D.create(x[0], x[1], x[2])
        return intersection_point
    except Exception as e:
        ui.messageBox(f'Error computing intersection point: {str(e)}')
        return None


def solve_linear_system(A, b):
    """
    Solves the linear system A x = b for x using Cramer's rule.

    Args:
        A (list of list of float): Coefficient matrix (3x3).
        b (list of float): Right-hand side vector (length 3).

    Returns:
        list of float: Solution vector x.
    """

    def determinant(matrix):
        return (matrix[0][0]*(matrix[1][1]*matrix[2][2] - matrix[1][2]*matrix[2][1]) -
                matrix[0][1]*(matrix[1][0]*matrix[2][2] - matrix[1][2]*matrix[2][0]) +
                matrix[0][2]*(matrix[1][0]*matrix[2][1] - matrix[1][1]*matrix[2][0]))

    D = determinant(A)
    if abs(D) < 1e-6:
        raise ValueError('Singular matrix')

    x = []
    for i in range(3):
        Ai = deepcopy(A)
        for j in range(3):
            Ai[j][i] = b[j]
        Di = determinant(Ai)
        xi = Di / D
        x.append(xi)

    return x

def create_tube(circle_geom, intersection_point, baseFeat):
    """
    Creates a tube from the circle to the intersection point.

    Args:
        circle_geom (dict): Dictionary containing 'center_point', 'normal_vector', and 'radius'.
        intersection_point (adsk.core.Point3D): The point to which the tube extends.
    """
    center_point = circle_geom['center_point']
    normal_vector = circle_geom['normal_vector']
    radius = circle_geom['radius']

    # Wall thickness (convert 4 mm to cm if units are cm)
    wall_thickness = 0.4  # 4 mm wall thickness (0.4 cm)

    path_sketch = newComp.sketches.add(rootComp.xYConstructionPlane)
    path_sketch.is3D = True

    path_line = path_sketch.sketchCurves.sketchLines.addByTwoPoints(center_point, intersection_point)

    # # Create a base feature to contain the 3D line
    # base_feature = rootComp.features.baseFeatures.add()
    # base_feature.startEdit()

    # # Create the transient Line3D geometry
    # line3d = adsk.core.Line3D.create(center_point, intersection_point)

    # # Create the BRepWire using the transient geometry
    # temp_brep_manager = adsk.fusion.TemporaryBRepManager.get()
    # wireBody, edgeMap = temp_brep_manager.createWireFromCurves([line3d])
    # wireEdges = wireBody.edges
    # edgeForCol = wireEdges.item(0).createForAssemblyContext(newOccu)
    # col = adsk.core.ObjectCollection.create()
    # futil.log(f'{wireEdges.item(0).objectType}')
    # col.add(edgeForCol)
    
    # # # Add the wire to the base feature
    # # wire_body = baseFeat.add(brep_wire)

    # # # Finish editing the base feature
    # # base_feature.finishEdit()
    
    # # Get the edge from the body to use in the path
    # futil.log(f'{wireBody.edges.count}')
    # # edges = adsk.core.ObjectCollection.createWithArray(edgeMap)
    # # edge = edgeMap(0)
    # # futil.log(f'{wireBody.edges.item(0).objectType}')
    # # Create a path from the edge
    path = newComp.features.createPath(path_line,False)

    # Create a plane at the circle's center with normal vector along the path direction
    direction_vector = adsk.core.Vector3D.create(
        intersection_point.x - center_point.x,
        intersection_point.y - center_point.y,
        intersection_point.z - center_point.z
    )
    direction_vector.normalize()
    plane = adsk.core.Plane.create(center_point, direction_vector)

    # Create a construction plane at the circle's center with the plane we just created
    planes = newComp.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByPlane(plane)
    profile_plane = planes.add(plane_input)

    # Create a sketch on the profile plane
    profile_sketch = newComp.sketches.add(profile_plane)
    sketch_center_point = profile_sketch.modelToSketchSpace(center_point)
    # Draw two concentric circles representing the tube cross-section
    sketch_circles = profile_sketch.sketchCurves.sketchCircles
    # Inner circle (matches circle's radius)
    inner_circle = sketch_circles.addByCenterRadius(sketch_center_point, radius)
    # Outer circle (radius + wall thickness)
    outer_circle = sketch_circles.addByCenterRadius(sketch_center_point, radius + wall_thickness)

    # Get the profile of the ring
    profiles = profile_sketch.profiles
    if profiles.count == 0:
        ui.messageBox('No profile found in the sketch.')
        return
    profile = profiles.item(1)

    # Create a sweep input
    sweeps = newComp.features.sweepFeatures
    sweep_input = sweeps.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    # Set the orientation
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType

    # Create the sweep
    sweep = sweeps.add(sweep_input)


# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
    futil.log(f'{CMD_NAME} Command Destroy Event')


