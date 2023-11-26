import ifcopenshell
import ifcopenshell.util
import ifcopenshell.util.element
import ifcopenshell.util.selector
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.api

import time

import math
import numpy as np


from bokeh.models import ColumnDataSource, LabelSet
from bokeh.plotting import figure, show
from bokeh.sampledata.periodic_table import elements
from bokeh.models import Label

from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary
from topologicpy.Plotly import Plotly

import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Install the folowwing packages on your computer using the Command Prompt
# pip install topologic
# pip install topologicpy
# pip install bokeh
# pip install numpy
# pip install selenium
# pip install ifcopenshell


###########################################################
# ------ Import model ------#
model = ifcopenshell.open(
    "LLYN - STRU.ifc"
)  # The script from DTU Learn did not work for us - bpy module could not be loaded using pip
# If this script and the IFC file are in the same folder it works like this :)
###########################################################


while True:
    try:
        user_input = str(
            input(
                "Please type columns or beams depending on what you want to investigate: "
            )
        )
        if user_input not in ["columns", "beams"]:
            raise ValueError
        print(f"Great Choice! Lets investigate some {user_input}.")
        break
    except ValueError:
        print("Invalid input. Please enter -columns- or -beams-.")

if user_input == "columns":
    ###########################################################
    # ------ Check how many columns in total ------#
    columns_in_model = 0

    for entity in model.by_type("IfcColumn"):
        columns_in_model += 1

    print(f"\nThere are {columns_in_model} columns in the model")
    ###########################################################

    ###########################################################
    # ------ Check how many different column types ------#
    columns = model.by_type("IfcColumn")
    names = [
        ifcopenshell.util.selector.get_element_value(column, "type.Name")
        for column in columns
    ]
    unique_names = set(names)

    i = 0
    for name in unique_names:
        print(f"There are {names.count(name)} {name} columns in the structure")
        i += names.count(name)

    if i == columns_in_model:
        print("All columns where detected!")
    else:
        print(f"{columns_in_model - i} columns are missing")
    ###########################################################

    ###########################################################
    # ------ Define functions used later on ------#

    # Calculates area of random polygon #
    def shoelace_formula(points):
        n = len(points)
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += (points[i][0] * points[j][1]) - (points[j][0] * points[i][1])
        area = round(abs(area) / 2, 8)  # m2
        return area

    # Calculates centroid of random polygon #
    def calculate_centroid(points):
        n = len(points)
        if n == 0:
            return None

        # Calculate the sums of x and y coordinates
        sum_x = sum(point[0] for point in points)
        sum_y = sum(point[1] for point in points)

        # Calculate the centroid coordinates
        centroid_x = sum_x / n
        centroid_y = sum_y / n

        return [centroid_x, centroid_y]

    # Calculates polar angle used for sorting points polar #
    def polar_angle(point):
        x, y = point[0], point[1]
        return math.atan2(y - center_y, x - center_x)

    # Calculates distance between 2 points #
    def calculate_distance(point1, point2):
        x1, y1 = point1[0], point1[1]
        x2, y2 = point2[0], point2[1]
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return distance

    ###########################################################

    ###########################################################
    # ------ Create empty lists and dictionaries to store properties ------#

    # List to store length #
    column_length_beton = []
    column_length_steel = []
    column_length_opstrop = []

    # Dictionaries to store points
    concrete_points = {}
    steel_points = {}
    opstrop_points = {}

    # MAIN DICTIONARY - used to store properties of all columns #
    properties = {}

    ###########################################################

    ###########################################################
    # ------ Calculate dimensions and geomtric crosssection properties from all columns ------#

    # Find all columns #
    columns = model.by_type("IfcColumn")
    i = 0

    # Iterate through all columns and store properties in MAIN DICTIONARY (properties) #
    for column in columns:
        ID = ifcopenshell.util.selector.get_element_value(column, "Tag")

        ifc_file = model
        element = column

        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, element)

        matrix = shape.transformation.matrix.data

        matrix = ifcopenshell.util.shape.get_shape_matrix(shape)

        location = matrix[:, 3][0:3]

        # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
        verts = shape.geometry.verts

        # Indices of vertices per edge e.g. [e1v1, e1v2, e2v1, e2v2, ...]
        edges = shape.geometry.edges

        # Indices of vertices per triangle face e.g. [f1v1, f1v2, f1v3, f2v1, f2v2, f2v3, ...]
        faces = shape.geometry.faces

        # Since the lists are flattened, you may prefer to group them like so depending on your geometry kernel
        # A nested numpy array e.g. [[v1x, v1y, v1z], [v2x, v2y, v2z], ...]
        grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)

        # First loop to detect SHS shaped columns
        if "SHS" in ifcopenshell.util.selector.get_element_value(column, "type.Name"):
            i += 1

            ID = ifcopenshell.util.selector.get_element_value(column, "Tag")

            steel_points[ID] = [ID]
            properties[ID] = [ID]

            sorted_list = sorted(grouped_verts, key=lambda x: x[-1])

            # Calculate length of columns
            column_length_steel.append(sorted_list[-1][-1] - sorted_list[0][-1])

            # Split points up in inner and outer section - because SHS is a hollow section
            section = sorted_list[0:4]
            section_2 = sorted_list[4:8]

            # Normalize points so the left bottom corner of the section starts in (0,0)
            min_x = min(point[0] for point in section)
            min_y = min(point[1] for point in section)

            normalized_points = [
                [point[0] - min_x, point[1] - min_y, point[2]] for point in section
            ]
            normalized_points2 = [
                [point[0] - min_x, point[1] - min_y, point[2]] for point in section_2
            ]

            # Define the center of the polygon - used for the calculation of the polar angle
            center_x = round(calculate_centroid(normalized_points)[0], 3)
            center_y = round(calculate_centroid(normalized_points)[1], 3)

            # Sort points polar to have inner and outer points aligned - prevents mistakes in calculating geometric properties
            sorted_points = sorted(normalized_points, key=polar_angle)
            normalized_points = sorted_points

            sorted_points2 = sorted(normalized_points2, key=polar_angle)
            normalized_points2 = sorted_points2

            # Get x and y coordinates to input in graph
            x_coords = [point[0] for point in normalized_points]
            y_coords = [point[1] for point in normalized_points]

            x_coords2 = [point[0] for point in normalized_points2]
            y_coords2 = [point[1] for point in normalized_points2]

            # Calculate area using above defined formula
            enclosed_area = (
                shoelace_formula(normalized_points[0:5])
                - shoelace_formula(normalized_points2[0:5])
            ) * 1000000

            # Calculate all geometric section properties
            bi = round(
                abs(normalized_points2[0][0] - normalized_points2[1][0]) * 1000, 3
            )
            hi = round(
                abs(normalized_points2[0][1] - normalized_points2[3][1]) * 1000, 3
            )

            be = round(abs(normalized_points[0][0] - normalized_points[1][0]) * 1000, 3)
            he = round(abs(normalized_points[0][1] - normalized_points[3][1]) * 1000, 3)

            t1 = round(
                abs(normalized_points2[0][0] - normalized_points[0][0]) * 1000, 3
            )
            t2 = round(
                abs(normalized_points2[0][1] - normalized_points[0][1]) * 1000, 3
            )

            # Moment of inertia
            Iz = round(((1 / 12) * be * he**3) - ((1 / 12) * bi * hi**3), 7)
            Iy = round(((1 / 12) * he * be**3) - ((1 / 12) * hi * bi**3), 7)

            # Append calculated properties to MAIN DICTIONARY
            properties[ID].append(enclosed_area)
            properties[ID].append(Iy)
            properties[ID].append(Iz)
            properties[ID].append(column_length_steel[0])

            # Set description for graph
            name = str(
                ifcopenshell.util.selector.get_element_value(column, "type.Name")
            )
            text = f"  Cross-section properties \n \n  Type: {name} \n  bi = {bi} mm \n  be = {be} mm \n  hi = {hi} mm \n  he = {he} mm \n  t1 = {t1} mm \n  t2 = {t2} mm \n  A = {enclosed_area} mm2 \n  Iy = {Iy} mm4 \n  Iz = {Iz} mm4 \n  span = {round(column_length_steel[0],3)} m \n "
            properties[ID].append(text)

            # Append start point to end for drawing a closed line in the graph
            normalized_points.append(normalized_points[0])
            normalized_points2.append(normalized_points2[0])

            # Get all x and y coordinates to input in graph
            x_coords = [point[0] for point in normalized_points]
            y_coords = [point[1] for point in normalized_points]

            x_coords2 = [point[0] for point in normalized_points2]
            y_coords2 = [point[1] for point in normalized_points2]

            # Append coordinates to dictionary to store and use later on
            steel_points[ID].append(x_coords)
            steel_points[ID].append(y_coords)
            steel_points[ID].append(x_coords2)
            steel_points[ID].append(y_coords2)

        # Loop for round section
        if "stropning" in str(
            ifcopenshell.util.selector.get_element_value(column, "type.Name")
        ):
            i += 1

            opstrop_points[ID] = [ID]
            properties[ID] = [ID]

            # Calculate length of columns
            column_length_opstrop.append(sorted_list[-1][-1] - sorted_list[0][-1])

            sorted_list = sorted(grouped_verts, key=lambda x: x[-1])

            # Get all points for one section
            section = sorted_list[0:26]

            # Normalize points to start at (0, 0)
            min_x = min(point[0] for point in section)
            min_y = min(point[1] for point in section)

            normalized_points = [
                [point[0] - min_x, point[1] - min_y, point[2]] for point in section
            ]

            # Define the center of the circle - for polar angles
            center_x = round(calculate_centroid(normalized_points)[0], 3)
            center_y = round(calculate_centroid(normalized_points)[1], 3)

            section = normalized_points

            # Sort the points based on polar angles and add first point to the end for a closed line
            sorted_points = sorted(section, key=polar_angle)
            sorted_points.append(sorted_points[0])

            section = sorted_points

            # Calculate section properties
            radius = round(
                calculate_distance(normalized_points[0], [center_x, center_y]) * 1000, 1
            )
            Iy = round((np.pi * (2 * radius) ** 4) / 64, 3)
            Iz = Iy

            # Calculate area - Here the shoelace formula is not used due to the circle being approximated as a polygon! Therefore radius formula is more precise :)
            enclosed_area = round(
                np.pi
                * (
                    calculate_distance(normalized_points[0], [center_x, center_y])
                    * 1000
                )
                ** 2,
                2,
            )

            # Get all x any y coordinates for graph
            y_points = [point[1] for point in section]
            x_points = [point[0] for point in section]

            # Set description for graph
            name = str(
                ifcopenshell.util.selector.get_element_value(column, "type.Name")
            )
            Id = str(ifcopenshell.util.selector.get_element_value(column, "Tag"))
            text = f"  Cross-section properties \n \n Type: {name} \n  r = {radius} mm \n  A = {enclosed_area} mm2 \n  Iy,Iz = {Iy} mm4 \n  span = {round(column_length_opstrop[0],3)} m \n "

            # Append coordinates to dictionary to store and use later on
            opstrop_points[ID].append(y_points)
            opstrop_points[ID].append(x_points)

            # Append calculated properties to MAIN DICTIONARY
            properties[ID].append(enclosed_area)
            properties[ID].append(Iy)
            properties[ID].append(Iz)
            properties[ID].append(column_length_opstrop[0])
            properties[ID].append(text)

        # Loop for every rectangular concrete section
        if "Beton" in str(column[2]):
            i += 1

            ID = ifcopenshell.util.selector.get_element_value(column, "Tag")

            concrete_points[ID] = [ID]
            properties[ID] = [ID]

            sorted_list = sorted(grouped_verts, key=lambda x: x[-1])

            # Calculate coulmn length
            column_length_beton.append(sorted_list[-1][-1] - sorted_list[0][-1])

            # Get corner points for each section
            section = sorted_list[0:4]

            # Normalize points to start at (0, 0)
            min_x = min(point[0] for point in section)
            min_y = min(point[1] for point in section)

            normalized_points = [
                [point[0] - min_x, point[1] - min_y, point[2]] for point in section
            ]

            normalized_points.append(normalized_points[0])
            section = normalized_points

            # Calculate area
            enclosed_area = shoelace_formula(section) * 1000000

            # width and height
            b = round(abs(section[1][1] - section[0][1]) * 1000, 3)
            h = round(abs(section[1][0] - section[2][0]) * 1000, 3)

            # moment of inertia calculation
            Iz = round((1 / 12) * b * h**3 + enclosed_area * 0, 7)
            Iy = round((1 / 12) * h * b**3 + enclosed_area * 0, 7)

            properties[ID].append(enclosed_area)
            properties[ID].append(Iy)
            properties[ID].append(Iz)
            properties[ID].append(column_length_beton[0])

            # Set description for graph
            name = str(
                ifcopenshell.util.selector.get_element_value(column, "type.Name")
            )
            text = f"  Cross-section properties \n  \n  Type: {name} \n  b = {b} mm \n  h = {h} mm \n  A = {round(enclosed_area,3)} mm2 \n  Iy = {Iy} mm4 \n  Iz = {Iz} mm4  \n  Span = {round(column_length_beton[0],3)} m  \n     "

            # concrete_properties[ID].append(text)
            properties[ID].append(text)

            # Get all x any y coordinates for graph
            y_points = [point[1] for point in section]
            x_points = [point[0] for point in section]

            # Append coordinates to dictionary to store and use later on
            concrete_points[ID].append(y_points)
            concrete_points[ID].append(x_points)

            # Append calculated properties to MAIN DICTIONARY

    ###########################################################

    # Check if all columns were detected and processed in the loop
    if i == columns_in_model:
        print(
            f"All {i} columns were processed and their geometric properties calculated"
        )

    while True:
        try:
            export_input = str(
                input("Do you want to export the data to the IFC file ? (yes or no): ")
            )
            if export_input.strip().lower() not in ["yes", "no"]:
                raise ValueError()
            break
        except ValueError:
            print("Invalid input. Please enter yes or no.")

    if export_input == "yes":
        ifc_file = model
        for element in model.by_type("IfcColumn"):
            ID = ifcopenshell.util.selector.get_element_value(element, "Tag")
            pset = ifcopenshell.api.run(
                "pset.add_pset", model, product=element, name="Geometric cs-properties"
            )
            ifcopenshell.api.run(
                "pset.edit_pset",
                model,
                pset=pset,
                properties={
                    "Area": f"{properties[ID][1]} mm2",
                    "Iy": f"{properties[ID][2]} mm4",
                    "Iz": f"{properties[ID][3]} mm4",
                },
            )
        model.write("updated_column_properties.ifc")
        print()
        print("Model was updated succesfully and saved in the same folder.")
    if export_input == "no":
        print("Model was not updated.")

    # --!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!--#
    # Investigate one column by displaying its cross section in a graph and analyze it for forces and deflection

    # ------ Choose column to investigate by changing the index! ------#

    while True:
        try:
            check = [
                str(ifcopenshell.util.selector.get_element_value(col, "Tag"))
                for col in model.by_type("IfcColumn")
            ]
            input_ = int(
                input(
                    "Please type desired column Tag-id to view properties and graph (Tags can be found in the model in blender): "
                )
            )

            if str(input_) in check:
                print("Column Tag-id exists and will be processed :)")
                break
            else:
                print("Tag-id does not exist - please try again")

        except ValueError:
            print("Invalid input. Please enter only integers.")

    for col in model.by_type("IfcColumn"):
        if str(input_) == str(ifcopenshell.util.selector.get_element_value(col, "Tag")):
            column = col

    ID = ifcopenshell.util.selector.get_element_value(column, "Tag")

    # --!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!--#

    # ------ View 3D topology of column ------#

    if "Opstrop" not in str(
        ifcopenshell.util.selector.get_element_value(column, "type.Name")
    ):
        I = ifcopenshell.util.selector.get_element_value(column, "GlobalId")

        topo_all = Topology.ByIFCFile(model, True)

        for topo in topo_all:
            dict_ = Topology.Dictionary(topo)
            list_ = Dictionary.Values(dict_)

            if list_ == None:
                continue

            if list_ != None:
                if list_[0] == I:
                    topo_column = topo
                    fig = Plotly.FigureByTopology(topo_column, renderer="chrome")
                    Plotly.Show(
                        fig, camera=[5, 5, 5], renderer="browser", target=None, up=None
                    )

    if "SHS" in ifcopenshell.util.selector.get_element_value(column, "type.Name"):
        # Set figure for graph display
        TITLE = f"Cross-section of column {ID}"
        TOOLS = "hover,pan,wheel_zoom,box_zoom,reset,save"

        p = figure(tools=TOOLS, toolbar_location="above", width=600, title=TITLE)
        p.toolbar.logo = "grey"
        p.background_fill_color = "#efefef"
        p.xaxis.axis_label = "y [m]"
        p.yaxis.axis_label = "z [m]"
        p.grid.grid_line_color = "white"

        # Define scatter plot with points
        p.scatter(
            steel_points[ID][1],
            steel_points[ID][2],
            size=12,
            color="melting_colors",
            line_color="black",
            alpha=1.0,
        )

        # Define scatter plot with points
        p.scatter(
            steel_points[ID][3],
            steel_points[ID][4],
            size=12,
            color="melting_colors",
            line_color="black",
            alpha=1.0,
        )

        # Define line plot with points
        p.line(steel_points[ID][3], steel_points[ID][4], line_width=2)
        p.line(steel_points[ID][1], steel_points[ID][2], line_width=2)

        source = ColumnDataSource(elements)

        labels = LabelSet(
            x="x coord",
            y="y coord",
            text="symbol",
            text_font_size="11px",
            text_color="#000000",
            source=source,
            text_align="center",
        )
        p.add_layout(labels)

        # Add text with geometric cross section properties
        p.add_layout(
            Label(
                x=steel_points[ID][3][3],
                y=steel_points[ID][3][3],
                text=properties[ID][5],
                text_color="#000000",
                text_font_size="11px",
            )
        )

        show(p)

        # Variables for further structural analysis
        span = properties[ID][4]
        Iy = properties[ID][2]
        Iz = properties[ID][3]
        A = properties[ID][1]

    if "stropning" in ifcopenshell.util.selector.get_element_value(column, "type.Name"):
        # Set figure for graph display
        TITLE = f"Cross-section of column {ID}"
        TOOLS = "hover,pan,wheel_zoom,box_zoom,reset,save"

        p = figure(tools=TOOLS, toolbar_location="above", width=600, title=TITLE)
        p.toolbar.logo = "grey"
        p.background_fill_color = "#efefef"
        p.xaxis.axis_label = "y [m]"
        p.yaxis.axis_label = "z [m]"
        p.grid.grid_line_color = "white"

        source = ColumnDataSource(elements)

        # Define scatter plot with points
        p.scatter(
            opstrop_points[ID][2],
            opstrop_points[ID][1],
            size=12,
            color="melting_colors",
            line_color="black",
            alpha=1.0,
        )

        # Define line plot with points
        p.line(opstrop_points[ID][2], opstrop_points[ID][1], line_width=2)

        labels = LabelSet(
            x="x coord",
            y="y coord",
            text="symbol",
            text_font_size="11px",
            text_color="#000000",
            source=source,
            text_align="center",
        )
        p.add_layout(labels)

        # Add text with geometric cross section propertie
        p.add_layout(
            Label(
                x=opstrop_points[ID][2][20],
                y=opstrop_points[ID][2][20],
                text=properties[ID][5],
                text_color="#000000",
                text_font_size="11px",
            )
        )

        show(p)

    if "Beton" in ifcopenshell.util.selector.get_element_value(column, "type.Name"):
        # Set figure for graph display
        TITLE = f"Cross-section of column {ID}"
        TOOLS = "hover,pan,wheel_zoom,box_zoom,reset,save"

        p = figure(tools=TOOLS, toolbar_location="above", width=600, title=TITLE)
        p.toolbar.logo = "grey"
        p.background_fill_color = "#efefef"
        p.xaxis.axis_label = "y [m]"
        p.yaxis.axis_label = "z [m]"
        p.grid.grid_line_color = "white"

        source = ColumnDataSource(elements)

        # Define scatter plot with points
        p.scatter(
            concrete_points[ID][1],
            concrete_points[ID][2],
            size=12,
            color="melting_colors",
            line_color="black",
            alpha=1.0,
        )

        # Define line plot with points
        p.line(concrete_points[ID][1], concrete_points[ID][2], line_width=2)

        labels = LabelSet(
            x="x coord",
            y="y coord",
            text="symbol",
            text_font_size="11px",
            text_color="#000000",
            source=source,
            text_align="center",
        )
        p.add_layout(labels)

        # Add text with geometric cross section propertie
        p.add_layout(
            Label(
                x=0,
                y=0,
                text=properties[ID][5],
                text_color="#000000",
                text_font_size="11px",
            )
        )

        # Variables for further structural analysis

        show(p)


if user_input == "beams":
    beams = model.by_type("IfcBeam")

    beam_dictionary = {}
    beam_type_dictionary = {}

    number_of_beams = len(beams)

    print(f"\nThere are {number_of_beams} beams in the model.")

    total_beam_length = 0
    while True:
        try:
            large_span_beam_min = float(input("Find beams longer than (in mm): "))
            # if large_span_beam_min is not float:
            # raise ValueError()
            break
        except ValueError:
            print("Invalid input. Please type a number.")

    large_beams = 0

    print()
    print(f"Beams larger than {large_span_beam_min} mm: ")

    # Get beam ID, beam type, span, large beams and dictionary of beams.
    for beam in beams:
        beam_id = ifcopenshell.util.selector.get_element_value(beam, "Tag")
        beam_type = ifcopenshell.util.element.get_type(beam)
        psets = ifcopenshell.util.element.get_psets(beam_type)
        description = psets["Pset_ReinforcementBarPitchOfBeam"]["Description"]
        for definition in beam.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByProperties"):
                property_set = definition.RelatingPropertyDefinition
                if property_set.Name == "Pset_BeamCommon":
                    for property in property_set.HasProperties:
                        if property.Name == "Span":
                            span_beam = float(property.NominalValue.wrappedValue)
                            total_beam_length += span_beam

                            beam_dictionary.update(
                                {
                                    float(beam_id): {
                                        "Span": span_beam,
                                        "Type": description,
                                    }
                                }
                            )

                            if (
                                property.NominalValue.wrappedValue
                                >= large_span_beam_min
                            ):
                                large_beams += 1
                                print(f"ID: {beam_id}")
                                print(
                                    f"Beam span: {property.NominalValue.wrappedValue}"
                                )
                                print(
                                    ifcopenshell.util.element.get_material(
                                        beam, "Material.Name"
                                    )[0]
                                )
                                print()

    print(
        f"There are {large_beams} beams in the model larger than {large_span_beam_min/1000} meters."
    )

    print(f"\nThere are {total_beam_length/1000} meters of beam in the model.")

    # Get the number of horizontal, tilted and vertical beams
    horizontal_beams = []
    tilted_beams = []
    vertical_beams = []

    for beam in beams:
        for definition in beam.IsDefinedBy:
            if definition.is_a("IfcRelDefinesByProperties"):
                property_set = definition.RelatingPropertyDefinition
                if property_set.Name == "Pset_BeamCommon":
                    beam_slope = next(
                        p.NominalValue.wrappedValue
                        for p in property_set.HasProperties
                        if p.Name == "Slope"
                    )
                    beam_roll = next(
                        p.NominalValue.wrappedValue
                        for p in property_set.HasProperties
                        if p.Name == "Roll"
                    )

                    if beam_slope > 0:
                        tilted_beams.append(beam)
                    elif beam_roll == 90:
                        vertical_beams.append(beam)
                    else:
                        horizontal_beams.append(beam)

    print(f"Number of horizontal beams: {len(horizontal_beams)}")

    print(f"Number of vertical beams: {len(vertical_beams)}")

    print(f"Number of tilted beams: {len(tilted_beams)}")
    print()
    print()

    print("Please wait 2 min for me to fetch the beam data from the website :)")
    start_time = time.time()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)

    # Dictionary with endings specific to the website's url.
    url_parameter_dictionary = {
        "l": "-en-10056-1-2017-arcelormittal-2018",
        "ipe": "-din-1025-5-1994-03-euronorm-19-57",
        "upe": "-en-10365-2017-arcelormittal-2018",
        "rhs": "-en-10219-2-alukonigstahl",
        "shs": "-en-10219-2-condesa",
        "heb": "-din-1025-2-1995-11-euronorm-53-62",
    }

    # Get the url of the right beam for the website.
    def get_url_from_description(des):
        results = re.findall("[A-Z]*(?![a-z])[0-9x]*[A-Z]*(?![a-z])", des)
        beam_type_code = "-".join([result for result in results if result]).lower()
        if not "-" in beam_type_code:
            beam_type_code = (
                "".join(re.findall("[a-wy-z]", beam_type_code))
                + "-"
                + "".join(re.findall("[0-9x]", beam_type_code))
            )
        key = beam_type_code.split("-")[0]
        url = f"https://www.dlubal.com/en/cross-section-properties/{beam_type_code}{url_parameter_dictionary[key]}"
        return url

    # Get the data of the beam type from the website.
    def get_data_from_web(data_type):
        try:
            text_content = "Data not found."
            # Wait for up to 20 seconds for the element to be located
            element = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        f"//td[@class='tsl-dim' and contains(text(), '{data_type}')]/following-sibling::td[2]",
                    )
                )
            )
            text_content = element.text
        except Exception as e:
            # print("Element not found within the specified time")
            pass
        finally:
            return text_content

    # Get the type of the beam.

    done_beams = []

    for beam in beams:
        beam_id = ifcopenshell.util.selector.get_element_value(beam, "Tag")
        beam_type = ifcopenshell.util.element.get_type(beam)
        psets = ifcopenshell.util.element.get_psets(beam_type)
        description = psets["Pset_ReinforcementBarPitchOfBeam"]["Description"]

        # Skip if already got datas.
        if description in done_beams:
            continue
        done_beams.append(description)

        if "I-profil" in description:
            # print("This is a unique beam.")
            continue

        url = get_url_from_description(description)
        # visit url
        driver.get(url)

        area = get_data_from_web("Sectional area")
        thickness = get_data_from_web("hickness")
        Iy = get_data_from_web("Area moment of inertia about y-axis")
        Iz = get_data_from_web("Area moment of inertia about z-axis")

        if Iz == "Data not found.":
            Iz = Iy

        beam_type_dictionary.update(
            {
                description: {
                    "Area": float(area),
                    "Thickness": float(thickness),
                    "Iy": float(Iy),
                    "Iz": float(Iz),
                }
            }
        )

    end_time = time.time()
    elapsed_time = end_time - start_time
    if elapsed_time < 2:
        print(
            f"Done with getting the all the data :) \nEven faster than the anticipated 2 min ({elapsed_time}s)!"
        )
    if elapsed_time > 2:
        print(
            f"Done with getting all the data :) \nSorry it took a bit longer than the anticipated 2 min ({elapsed_time}s)..... "
        )

    print()
    i = 0
    while True:
        try:
            export_input = str(
                input("Do you want to export the data to the IFC file ? (yes or no): ")
            )
            if export_input.strip().lower() not in ["yes", "no"]:
                raise ValueError()
            break
        except ValueError:
            print("Invalid input. Please enter -yes- or -no-.")
    import ifcopenshell.api

    if export_input == "yes":
        ifc_file = model
        keys = list(beam_dictionary.keys())
        for element in model.by_type("IfcBeam"):
            ID = ifcopenshell.util.selector.get_element_value(element, "Tag")
            beam_type = beam_dictionary[int(ID)]["Type"]
            if "Opsvejst" in str(beam_type):
                i += 1
                print(i)
                continue

            if "Opsvejst" not in str(beam_type):
                pset = ifcopenshell.api.run(
                    "pset.add_pset",
                    model,
                    product=element,
                    name="Geometrical cs-properties",
                )
                ifcopenshell.api.run(
                    "pset.edit_pset",
                    model,
                    pset=pset,
                    properties={
                        "Area": f"{beam_type_dictionary[beam_type]['Area']} cm2",
                        "Iy": f"{beam_type_dictionary[beam_type]['Iy']} cm4",
                        "Iz": f"{beam_type_dictionary[beam_type]['Iz']} cm4",
                    },
                )
        model.write("updated_beam_properties.ifc")
        print("Model was updated succesfully and saved in the same folder.")

    if export_input == "no":
        print("Model was not updated.")

    print("\nPossible Ids:")
    print(
        "\n".join(
            [
                str(int(key))
                for key in beam_dictionary.keys()
                if not "I-profil" in beam_dictionary[key]["Type"]
            ][:10]
        )
    )
    # Choose a beam and get the data.
    beam_id = input(
        "Give the Tag-ID of the beam you would like the data of or type 'done' if you are done (Tag can be found in the model in Blender):  "
    )
    while beam_id != "done":
        try:
            beam_id = int(beam_id)
            print(f"Span = {beam_dictionary[beam_id]['Span']} mm")
            print(f"Type: {beam_dictionary[beam_id]['Type']}")
            beam_type = beam_dictionary[beam_id]["Type"]

            print(f"Area = {beam_type_dictionary[beam_type]['Area']} cm2")
            print(f"Thickness = {beam_type_dictionary[beam_type]['Thickness']} mm")
            print(f"Iy = {beam_type_dictionary[beam_type]['Iy']} cm4")
            print(f"Iz = {beam_type_dictionary[beam_type]['Iz']} cm4")

            for beam in model.by_type("IfcBeam"):
                if str(beam_id) == str(
                    ifcopenshell.util.selector.get_element_value(beam, "Tag")
                ):
                    beam_ = beam

            ID = ifcopenshell.util.selector.get_element_value(beam_, "Tag")

            I = ifcopenshell.util.selector.get_element_value(beam_, "GlobalId")

            topo_all = Topology.ByIFCFile(model, True)

            for topo in topo_all:
                dict_ = Topology.Dictionary(topo)
                list_ = Dictionary.Values(dict_)

                if list_ == None:
                    continue

                if list_ != None:
                    if list_[0] == I:
                        topo_beam = topo
                        fig = Plotly.FigureByTopology(topo_beam, renderer="chrome")
                        Plotly.Show(
                            fig,
                            camera=[5, 5, 5],
                            renderer="browser",
                            target=None,
                            up=None,
                        )

        except:
            print("Try again :/")
        finally:
            beam_id = input(
                "Give the Tag-ID of the beam you would like the data of or type 'done' if you are done (Tag can be found in the model in Blender): "
            )
