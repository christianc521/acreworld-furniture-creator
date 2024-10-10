import math
import adsk.core
import adsk.fusion
import os
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface
design = app.activeProduct
rootComp = design.rootComponent

CMD_NAME = os.path.basename(os.path.dirname(__file__))
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = 'Creates a threaded cap on circular edges'
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
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    button_icons = os.path.join(ICON_FOLDER, 'buttons')
    inputs = args.command.commandInputs

    initial_value_dist = adsk.core.ValueInput.createByString('0.0 cm')
    initial_value_angle = adsk.core.ValueInput.createByString('0.0 rad')

    origin_point = adsk.core.Point3D.create(0, 0, 0)
    x_vector = adsk.core.Vector3D.create(1, 0, 0)
    y_vector = adsk.core.Vector3D.create(0, 1, 0)
    z_vector = adsk.core.Vector3D.create(0, 0, 1)

    selection_input = inputs.addSelectionInput('selection_input', 'Selection', 'Select a Plane')
    selection_input.addSelectionFilter('CircularEdges')
    selection_input.setSelectionLimits(1)


# This function will be called when the user clicks the OK button in the command dialog.
def command_execute(args: adsk.core.CommandEventArgs):

    futil.log(f'{CMD_NAME} Command Execute Event')
    inputs = args.command.commandInputs

    # Get the selection input
    selection_input = inputs.itemById('selection_input')
    selected_edge = selection_input.selection(0).entity

    # Check if the selected entity is a BRepEdge
    if isinstance(selected_edge, adsk.fusion.BRepEdge):
        edge_geometry = selected_edge.geometry

        # Check if the edge geometry is a Circle3D
        if isinstance(edge_geometry, adsk.core.Circle3D):
            futil.log('selected edge is a circle')
            center_point = edge_geometry.center
            normal_vector = edge_geometry.normal
            radius = edge_geometry.radius

    # create a base feature
    baseFeat = None
    if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        baseFeat = rootComp.features.baseFeatures.add()
    if baseFeat:
        baseFeat.startEdit()

    # Define wall thickness and cap height (in cm)
    wall_thickness = .4  # 4 mm wall thickness (0.4 cm)
    cap_height = 1.0      # 10 mm cap height (1.0 cm)
    overlap_amount = 0.5  # 5 mm overlap over dowel (0.5 cm)

    # Create a plane using the circle's center and normal
    plane = adsk.core.Plane.create(center_point, normal_vector)

    # Create a construction plane at the circle's location
    planes = rootComp.constructionPlanes
    planeInput = planes.createInput()
    planeInput.setByPlane(plane)
    construction_plane = planes.add(planeInput)

    # Create a new sketch on the construction plane
    sketches = rootComp.sketches
    sketch = sketches.add(construction_plane)

    # Transform the circle's center point into the sketch's coordinate system
    sketch_center_point = sketch.modelToSketchSpace(center_point)

    # Create the circles at the transformed center point
    sketch_circles = sketch.sketchCurves.sketchCircles
    outer_circle = sketch_circles.addByCenterRadius(sketch_center_point, radius + wall_thickness)
    inner_circle = sketch_circles.addByCenterRadius(sketch_center_point, radius)

    # Get the profiles defined by the circles
    ring_profile = None
    inner_profile = None
    for prof in sketch.profiles:
        if prof.profileLoops.count == 2:
            ring_profile = prof  # The ring between outer and inner circles
        elif prof.profileLoops.count == 1:
            # Check if this profile is the inner circle
            prof_centroid = prof.areaProperties().centroid
            distance_to_center = prof_centroid.distanceTo(sketch_center_point)
            if distance_to_center < 0.001:
                inner_profile = prof  # The area inside the inner circle

    # Ensure both profiles are found
    if ring_profile is None or inner_profile is None:
        ui.messageBox('Could not find the necessary profiles.')
        return

    # Create an extrusion input for the cap walls (ring profile)
    extrudes = rootComp.features.extrudeFeatures
    ext_input_walls = extrudes.createInput(ring_profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    # Create ValueInputs for distances
    cap_height_distance = adsk.core.ValueInput.createByReal(cap_height)
    overlap_distance = adsk.core.ValueInput.createByReal(overlap_amount)

    # Create distance extent definitions
    extent_distance_positive = adsk.fusion.DistanceExtentDefinition.create(cap_height_distance)
    extent_distance_negative = adsk.fusion.DistanceExtentDefinition.create(overlap_distance)

    # Taper angles are zero
    taper_angle_zero = adsk.core.ValueInput.createByString('0 deg')

    # Set the two sides extent for the cap walls
    ext_input_walls.setTwoSidesExtent(extent_distance_negative, extent_distance_positive, taper_angle_zero, taper_angle_zero)

    # Create the extrusion to form the cap walls
    cap_walls_extrusion = extrudes.add(ext_input_walls)
    cap_body = cap_walls_extrusion.bodies.item(0)

    # Now, extrude the inner circle profile in the negative direction to cap off the end
    ext_input_inner = extrudes.createInput(inner_profile, adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # Set the extent to overlap amount in the negative direction
    ext_input_inner.setOneSideExtent(extent_distance_negative, adsk.fusion.ExtentDirections.PositiveExtentDirection)

    # Set the target body to the cap body
    ext_input_inner.participantBodies = [cap_body]

    # Create the extrusion to cap off the end
    cap_end_extrusion = extrudes.add(ext_input_inner)

    # Add threading to the outer face
    # Find the outer cylindrical face
    # Optional: Add threading to the outer face
    # Find the outer cylindrical face
    outer_faces = cap_body.faces
    outer_radius = radius + wall_thickness
    for face in outer_faces:
        if isinstance(face.geometry, adsk.core.Cylinder):
            face_radius = face.geometry.radius
            if abs(face_radius - outer_radius) < 0.001:
                # Apply threading to this face
                threads = rootComp.features.threadFeatures
                thread_data_query = threads.threadDataQuery
                threadTypes = thread_data_query.allThreadTypes
                futil.log(f"{threadTypes}")
                thread_type = 'ISO Metric profile'  # Specify your thread type
                is_internal = False  # False for external threads
                # Calculate the outer diameter (in mm if units are cm)
                outer_diameter_mm = (outer_radius * 2) * 10  # Convert cm to mm
                # Get all available sizes for the thread type and isInternal
                all_sizes = thread_data_query.allSizes(threadTypes[10])
                size = None
                # Find the closest matching size
                for s in all_sizes:
                    try:
                        # Remove any non-numeric characters (e.g., 'M')
                        thread_size = float(s.replace('M', '').split('x')[0])
                        if abs(thread_size - outer_diameter_mm) < 0.5:
                            size = s
                            break
                    except ValueError:
                        continue
                if size is None:
                    ui.messageBox('Could not find a suitable thread size.')
                    return
                # Get all designations for the matched size
                all_designations = thread_data_query.allDesignations(thread_type, size)
                # For simplicity, select the first designation
                designation = all_designations[0]

                allClasses = thread_data_query.allClasses(False, thread_type, designation)
                threadClass = allClasses[0]
                
                # Create the thread info
                thread_info = threads.createThreadInfo(is_internal, thread_type, designation, threadClass)
                thread_input = threads.createInput(face, thread_info)
                # Set threading properties
                thread_input.isFullLength = True
                thread_input.isModeled = True
                threads.add(thread_input)
                break

    if baseFeat:
        baseFeat.finishEdit()


# This function will be called when the user changes anything in the command dialog.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.input.parentCommand.commandInputs
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    # Get a reference to your command's inputs
    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('selection_input')
    distance_input: adsk.core.DistanceValueCommandInput = inputs.itemById('distance_input')
    bool_value_input: adsk.core.BoolValueCommandInput = inputs.itemById('bool_value_input')
    string_value_input: adsk.core.StringValueCommandInput = inputs.itemById('string_value_input')

    # create plane
    futil.log(f'{selection_input.selection(0).entity}')
    # Show and update the distance input when a plane is selected
    if changed_input.id == selection_input.id:
        if selection_input.selectionCount > 0:
            selection = selection_input.selection(0)
            selection_point = selection.point
            selected_entity = selection.entity
            plane = selected_entity.geometry

            distance_input.setManipulator(selection_point, plane.normal)
            distance_input.expression = "10mm * 2"
            distance_input.isEnabled = True
            distance_input.isVisible = True
        else:
            distance_input.isEnabled = False
            distance_input.isVisible = False

    # Enable edit on the string value input when the boolean is selected
    elif changed_input.id == bool_value_input.id:
        if bool_value_input.value:
            string_value_input.value = 'The Bool Value is checked'
        else:
            string_value_input.value = 'The Bool Value is not checked'


# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
    futil.log(f'{CMD_NAME} Command Destroy Event')


