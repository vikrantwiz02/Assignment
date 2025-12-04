import adsk.core, adsk.fusion, traceback
import math

# ==============================================================================
# HEXCORE BRAILLE EMBOSSER - PRECISION MATCH TO REFERENCE IMAGE
# ==============================================================================

# All dimensions in cm (Fusion 360 API requirement)
TOP_DIA = 6.0
TOP_PLATE_THICK = 0.5
SOLENOID_HOLE_DIA = 1.2
SOLENOID_RADIAL = 2.3
HEAD_HEIGHT = 6.0

# Braille configuration
BRAILLE_DOT = 0.15
BRAILLE_PITCH = 0.25

# Housing funnel stages (smooth transitions)
STAGE1_Z = -1.5
STAGE1_DIA = 5.2
STAGE2_Z = -3.2
STAGE2_DIA = 3.6
STAGE3_Z = -4.8
STAGE3_DIA = 2.4
BOTTOM_Z = -HEAD_HEIGHT
BOTTOM_DIA = 2.0

# Central support
CENTRAL_DIA = 1.4
CENTRAL_HEIGHT = 4.5
CENTRAL_HOLE = 0.6

# Curved ribs (organic shape)
RIB_COUNT = 3
RIB_WIDTH = 0.4
RIB_INNER_R = 0.8
RIB_OUTER_R = 2.4

# Solenoid details
SOL_BODY_DIA = 1.1
SOL_BODY_HEIGHT = 2.0
SOL_FLANGE_DIA = 1.3
SOL_FLANGE_HEIGHT = 0.6
SOL_HOLE = 0.35

# Pin guides
PIN_DIA = 0.2
PIN_LENGTH = 2.0

# Output chamber
OUTPUT_WIDTH = 2.2
OUTPUT_HEIGHT = 1.2

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = app.activeProduct
        rootComp = design.rootComponent
        
        xyPlane = rootComp.xYConstructionPlane
        
        # Create all construction planes
        planes = setupConstructionPlanes(rootComp, xyPlane)
        
        # Build main housing with top plate
        topPlate, holeEdges = createTopPlate(rootComp, xyPlane)
        brailleDots = createBrailleGrid(rootComp, planes['bottom'])
        channels = createChannels(rootComp, holeEdges, brailleDots)
        housing = createHousingBody(rootComp, xyPlane, planes, topPlate)
        
        # Cut channels from housing
        cutChannelsFromHousing(rootComp, housing, channels)
        
        # Add support structures
        addCurvedRibs(rootComp, xyPlane, housing)
        addCentralSupport(rootComp, xyPlane, housing)
        addCentralHole(rootComp, xyPlane, housing)
        addOutputChamber(rootComp, planes['bottom'], housing)
        
        # Create solenoids and pins
        createSolenoids(rootComp, xyPlane)
        createPins(rootComp, planes['bottom'])
        
        ui.messageBox('Complete!')
        
    except:
        if ui:
            ui.messageBox('Error:\\n{}'.format(traceback.format_exc()))


def setupConstructionPlanes(rootComp, xyPlane):
    """Create all necessary construction planes"""
    planes = {'xy': xyPlane}
    
    # Stage planes for loft
    for name, offset in [('stage1', STAGE1_Z), ('stage2', STAGE2_Z), 
                         ('stage3', STAGE3_Z), ('bottom', BOTTOM_Z),
                         ('output', BOTTOM_Z - OUTPUT_HEIGHT)]:
        planeInput = rootComp.constructionPlanes.createInput()
        planeInput.setByOffset(xyPlane, adsk.core.ValueInput.createByReal(offset))
        planes[name] = rootComp.constructionPlanes.add(planeInput)
    
    return planes


def createTopPlate(rootComp, xyPlane):
    """Create top plate with holes"""
    sketch = rootComp.sketches.add(xyPlane)
    
    # Outer circle
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), TOP_DIA / 2.0)
    
    # 6 solenoid holes
    for i in range(6):
        a = math.radians(i * 60)
        x, y = SOLENOID_RADIAL * math.cos(a), SOLENOID_RADIAL * math.sin(a)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(x, y, 0), SOLENOID_HOLE_DIA / 2.0)
    
    # Extrude plate
    extrudes = rootComp.features.extrudeFeatures
    prof = sketch.profiles.item(0)
    extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extInput.setDistanceExtent(False, adsk.core.ValueInput.createByReal(TOP_PLATE_THICK))
    ext = extrudes.add(extInput)
    plate = ext.bodies.item(0)
    plate.name = "Top_Plate"
    
    # Add chamfer to top edge
    chamferEdges = adsk.core.ObjectCollection.create()
    for edge in plate.edges:
        if edge.geometry.curveType == adsk.core.Curve3DTypes.Circle3DCurveType:
            if abs(edge.geometry.radius - TOP_DIA/2.0) < 0.01:
                if abs(edge.boundingBox.maxPoint.z - TOP_PLATE_THICK) < 0.01:
                    chamferEdges.add(edge)
    
    if chamferEdges.count > 0:
        chamfers = rootComp.features.chamferFeatures
        chamferInput = chamfers.createInput2()
        chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(chamferEdges, adsk.core.ValueInput.createByReal(0.1), True)
        try:
            chamfers.add(chamferInput)
        except:
            pass
    
    # Get hole edges for lofting
    edges = []
    for face in plate.faces:
        if face.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
            for edge in face.edges:
                if edge.geometry.curveType == adsk.core.Curve3DTypes.Circle3DCurveType:
                    if abs(edge.boundingBox.maxPoint.z - TOP_PLATE_THICK) < 0.01:
                        if abs(edge.geometry.radius - SOLENOID_HOLE_DIA/2.0) < 0.01:
                            edges.append(edge)
    
    sketch.isVisible = False
    return plate, edges


def createBrailleGrid(rootComp, bottomPlane):
    """Create 2x3 Braille dot pattern"""
    sketch = rootComp.sketches.add(bottomPlane)
    dots = []
    
    for col in range(2):
        for row in range(3):
            x = (col - 0.5) * BRAILLE_PITCH
            y = (row - 1.0) * BRAILLE_PITCH
            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(x, y, 0), BRAILLE_DOT / 2.0)
            dots.append(circle.centerSketchPoint)
    
    sketch.isVisible = False
    return dots


def createChannels(rootComp, holeEdges, brailleDots):
    """Create 6 converging channels"""
    lofts = rootComp.features.loftFeatures
    channels = []
    
    for i in range(min(6, len(holeEdges))):
        loftInput = lofts.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        loftInput.isSolid = True
        loftInput.loftSections.add(holeEdges[i])
        loftInput.loftSections.add(brailleDots[i])
        loft = lofts.add(loftInput)
        if loft.bodies.count > 0:
            channels.append(loft.bodies.item(0))
    
    return channels


def createHousingBody(rootComp, xyPlane, planes, topPlate):
    """Create smooth funnel housing"""
    # Create stage profiles
    sketches = {}
    
    # Stage 1
    sketches['s1'] = rootComp.sketches.add(planes['stage1'])
    sketches['s1'].sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), STAGE1_DIA / 2.0)
    
    # Stage 2
    sketches['s2'] = rootComp.sketches.add(planes['stage2'])
    sketches['s2'].sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), STAGE2_DIA / 2.0)
    
    # Stage 3
    sketches['s3'] = rootComp.sketches.add(planes['stage3'])
    sketches['s3'].sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), STAGE3_DIA / 2.0)
    
    # Bottom
    sketches['bot'] = rootComp.sketches.add(planes['bottom'])
    sketches['bot'].sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), BOTTOM_DIA / 2.0)
    
    # Top profile from existing plate
    topSketch = rootComp.sketches.add(xyPlane)
    topSketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), TOP_DIA / 2.0)
    
    # Create multi-stage loft
    lofts = rootComp.features.loftFeatures
    loftInput = lofts.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    loftInput.isSolid = True
    loftInput.loftSections.add(topSketch.profiles.item(0))
    loftInput.loftSections.add(sketches['s1'].profiles.item(0))
    loftInput.loftSections.add(sketches['s2'].profiles.item(0))
    loftInput.loftSections.add(sketches['s3'].profiles.item(0))
    loftInput.loftSections.add(sketches['bot'].profiles.item(0))
    
    loft = lofts.add(loftInput)
    housing = loft.bodies.item(0)
    housing.name = "Housing"
    
    # Join top plate
    combines = rootComp.features.combineFeatures
    toolBodies = adsk.core.ObjectCollection.create()
    toolBodies.add(topPlate)
    combineInput = combines.createInput(housing, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combines.add(combineInput)
    
    # Hide sketches
    for sk in sketches.values():
        sk.isVisible = False
    topSketch.isVisible = False
    
    return housing


def cutChannelsFromHousing(rootComp, housing, channels):
    """Cut all channels from housing"""
    combines = rootComp.features.combineFeatures
    for channel in channels:
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(channel)
        combineInput = combines.createInput(housing, toolBodies)
        combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combineInput.isKeepToolBodies = False
        combines.add(combineInput)


def addCurvedRibs(rootComp, xyPlane, housing):
    """Add 3 curved organic ribs matching reference"""
    extrudes = rootComp.features.extrudeFeatures
    combines = rootComp.features.combineFeatures
    
    for i in range(RIB_COUNT):
        angle = math.radians(i * 120 + 30)
        
        # Create rib using two parallel splines
        ribSketch = rootComp.sketches.add(xyPlane)
        
        # Points for center line
        numPoints = 15
        points1 = adsk.core.ObjectCollection.create()
        points2 = adsk.core.ObjectCollection.create()
        
        for j in range(numPoints):
            t = j / (numPoints - 1)
            r = RIB_INNER_R + t * (RIB_OUTER_R - RIB_INNER_R)
            
            # Add slight curve for organic look
            curveOffset = 0.12 * math.sin(t * math.pi)
            adjustedAngle = angle + curveOffset
            
            # Calculate perpendicular offset for width
            perpAngle = adjustedAngle + math.pi / 2.0
            halfWidth = RIB_WIDTH / 2.0
            
            # Center point
            cx = r * math.cos(adjustedAngle)
            cy = r * math.sin(adjustedAngle)
            
            # Offset points on both sides
            x1 = cx + halfWidth * math.cos(perpAngle)
            y1 = cy + halfWidth * math.sin(perpAngle)
            x2 = cx - halfWidth * math.cos(perpAngle)
            y2 = cy - halfWidth * math.sin(perpAngle)
            
            points1.add(adsk.core.Point3D.create(x1, y1, 0))
            points2.add(adsk.core.Point3D.create(x2, y2, 0))
        
        # Create two parallel splines
        spline1 = ribSketch.sketchCurves.sketchFittedSplines.add(points1)
        spline2 = ribSketch.sketchCurves.sketchFittedSplines.add(points2)
        
        # Connect ends to close profile
        ribSketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.startSketchPoint.geometry, spline2.startSketchPoint.geometry)
        ribSketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.endSketchPoint.geometry, spline2.endSketchPoint.geometry)
        
        if ribSketch.profiles.count > 0:
            # Find the enclosed profile
            for prof in ribSketch.profiles:
                try:
                    if prof.areaProperties().area > 0:
                        extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                        extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(CENTRAL_HEIGHT))
                        ribExt = extrudes.add(extInput)
                        
                        if ribExt.bodies.count > 0:
                            toolBodies = adsk.core.ObjectCollection.create()
                            toolBodies.add(ribExt.bodies.item(0))
                            combineInput = combines.createInput(housing, toolBodies)
                            combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
                            combineInput.isKeepToolBodies = False
                            try:
                                combines.add(combineInput)
                            except:
                                pass
                        break
                except:
                    pass
        
        ribSketch.isVisible = False


def addCentralSupport(rootComp, xyPlane, housing):
    """Add central cylinder"""
    sketch = rootComp.sketches.add(xyPlane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), CENTRAL_DIA / 2.0)
    
    extrudes = rootComp.features.extrudeFeatures
    extInput = extrudes.createInput(sketch.profiles.item(0), 
                                     adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(CENTRAL_HEIGHT))
    ext = extrudes.add(extInput)
    
    if ext.bodies.count > 0:
        combines = rootComp.features.combineFeatures
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(ext.bodies.item(0))
        combineInput = combines.createInput(housing, toolBodies)
        combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
        combines.add(combineInput)
    
    sketch.isVisible = False


def addCentralHole(rootComp, xyPlane, housing):
    """Add central through hole"""
    sketch = rootComp.sketches.add(xyPlane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0, 0, 0), CENTRAL_HOLE / 2.0)
    
    extrudes = rootComp.features.extrudeFeatures
    extInput = extrudes.createInput(sketch.profiles.item(0), 
                                     adsk.fusion.FeatureOperations.CutFeatureOperation)
    extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(HEAD_HEIGHT + 2.0))
    extInput.participantBodies = [housing]
    extrudes.add(extInput)
    
    sketch.isVisible = False


def addOutputChamber(rootComp, bottomPlane, housing):
    """Add output chamber box"""
    sketch = rootComp.sketches.add(bottomPlane)
    
    half = OUTPUT_WIDTH / 2.0
    p1 = adsk.core.Point3D.create(-half, -half, 0)
    p2 = adsk.core.Point3D.create(half, -half, 0)
    p3 = adsk.core.Point3D.create(half, half, 0)
    p4 = adsk.core.Point3D.create(-half, half, 0)
    
    sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
    sketch.sketchCurves.sketchLines.addByTwoPoints(p2, p3)
    sketch.sketchCurves.sketchLines.addByTwoPoints(p3, p4)
    sketch.sketchCurves.sketchLines.addByTwoPoints(p4, p1)
    
    if sketch.profiles.count > 0:
        extrudes = rootComp.features.extrudeFeatures
        extInput = extrudes.createInput(sketch.profiles.item(0), 
                                         adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(OUTPUT_HEIGHT))
        ext = extrudes.add(extInput)
        
        if ext.bodies.count > 0:
            combines = rootComp.features.combineFeatures
            toolBodies = adsk.core.ObjectCollection.create()
            toolBodies.add(ext.bodies.item(0))
            combineInput = combines.createInput(housing, toolBodies)
            combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
            combines.add(combineInput)
    
    sketch.isVisible = False


def createSolenoids(rootComp, xyPlane):
    """Create 6 solenoid assemblies"""
    for i in range(6):
        a = math.radians(i * 60)
        x, y = SOLENOID_RADIAL * math.cos(a), SOLENOID_RADIAL * math.sin(a)
        
        # Body
        sketch = rootComp.sketches.add(xyPlane)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(x, y, 0), SOL_BODY_DIA / 2.0)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(x, y, 0), SOL_HOLE / 2.0)
        
        extrudes = rootComp.features.extrudeFeatures
        if sketch.profiles.count > 0:
            extInput = extrudes.createInput(sketch.profiles.item(0), 
                                             adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(SOL_BODY_HEIGHT))
            ext = extrudes.add(extInput)
            
            # Flange
            planeInput = rootComp.constructionPlanes.createInput()
            planeInput.setByOffset(xyPlane, adsk.core.ValueInput.createByReal(SOL_BODY_HEIGHT))
            flangePlane = rootComp.constructionPlanes.add(planeInput)
            
            fSketch = rootComp.sketches.add(flangePlane)
            fSketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(x, y, 0), SOL_FLANGE_DIA / 2.0)
            fSketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(x, y, 0), SOL_HOLE / 2.0)
            
            if fSketch.profiles.count > 0:
                extInput = extrudes.createInput(fSketch.profiles.item(0), 
                                                 adsk.fusion.FeatureOperations.JoinFeatureOperation)
                extInput.setDistanceExtent(True, adsk.core.ValueInput.createByReal(SOL_FLANGE_HEIGHT))
                extInput.participantBodies = [ext.bodies.item(0)]
                extrudes.add(extInput)
            
            fSketch.isVisible = False
        sketch.isVisible = False


def createPins(rootComp, bottomPlane):
    """Create 6 pin needles from output box in Braille pattern"""
    sketch = rootComp.sketches.add(bottomPlane)
    
    # Create 6 pins in 3 rows of 2 (Braille cell pattern)
    # Positioned within the output box area
    colSpacing = 0.5  # Horizontal spacing between columns
    rowSpacing = 0.5  # Vertical spacing between rows
    
    # 3 rows, 2 columns (like Braille dots)
    for row in range(3):
        for col in range(2):
            x = (col - 0.5) * colSpacing
            y = (row - 1.0) * rowSpacing
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(x, y, 0), PIN_DIA / 2.0)
    
    extrudes = rootComp.features.extrudeFeatures
    for prof in sketch.profiles:
        extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        # Negative distance to extrude downward from bottom plane
        extInput.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-PIN_LENGTH))
        extrude = extrudes.add(extInput)
        extrude.bodies.item(0).name = "Pin_Needle"
    
    sketch.isVisible = False
