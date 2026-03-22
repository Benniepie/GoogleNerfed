"""
Model exported as python.
Name : APv2024-10-16
Group : 
With QGIS : 33803
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class Apv20241016(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('atp_ap', 'ATP AP', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('new_ap', 'New AP', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('old_ap', 'Old AP', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('ukraine_provinces', 'Ukraine provinces', defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('New_line', 'new_line', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Old_line', 'Old_line', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('PinsAp', 'Pins AP', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('ApOutput', 'AP output', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(34, model_feedback)
        results = {}
        outputs = {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': parameters['new_ap'],
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 0.0002,
            'END_CAP_STYLE': 0,  # Round
            'INPUT': parameters['old_ap'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Delete holes
        alg_params = {
            'INPUT': parameters['atp_ap'],
            'MIN_AREA': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteHoles'] = processing.run('native:deleteholes', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': parameters['old_ap'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 0.0002,
            'END_CAP_STYLE': 0,  # Round
            'INPUT': parameters['new_ap'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Fix geometries
        alg_params = {
            'INPUT': parameters['ukraine_provinces'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'OVERLAY': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': parameters['New_line']
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['New_line'] = outputs['Difference']['OUTPUT']

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Union
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Difference']['OUTPUT'],
            'OVERLAY': None,
            'OVERLAY_FIELDS_PREFIX': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Union'] = processing.run('native:union', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'OVERLAY': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': parameters['Old_line']
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Old_line'] = outputs['Difference']['OUTPUT']

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': parameters['new_ap'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}

        # Samenvoegen
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Samenvoegen'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}

        # Multipart to singleparts
        alg_params = {
            'INPUT': outputs['Difference']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MultipartToSingleparts'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}

        # Points along geometry
        alg_params = {
            'DISTANCE': 0.006,
            'END_OFFSET': 0,
            'INPUT': outputs['MultipartToSingleparts']['OUTPUT'],
            'START_OFFSET': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PointsAlongGeometry'] = processing.run('native:pointsalonglines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(13)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['Union']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(14)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Samenvoegen']['OUTPUT'],
            'OVERLAY': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(15)
        if feedback.isCanceled():
            return {}

        # Multipart to singleparts
        alg_params = {
            'INPUT': outputs['Difference']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MultipartToSingleparts'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(16)
        if feedback.isCanceled():
            return {}

        # Union
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Difference']['OUTPUT'],
            'OVERLAY': None,
            'OVERLAY_FIELDS_PREFIX': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Union'] = processing.run('native:union', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(17)
        if feedback.isCanceled():
            return {}

        # Merge vector layers
        alg_params = {
            'CRS': None,
            'LAYERS': [outputs['Difference']['OUTPUT'],outputs['Difference']['OUTPUT']],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(18)
        if feedback.isCanceled():
            return {}

        # Verschil
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['PointsAlongGeometry']['OUTPUT'],
            'OVERLAY': outputs['Buffer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Verschil'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(19)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['Union']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(20)
        if feedback.isCanceled():
            return {}

        # Points along geometry
        alg_params = {
            'DISTANCE': 0.006,
            'END_OFFSET': 0,
            'INPUT': outputs['MultipartToSingleparts']['OUTPUT'],
            'START_OFFSET': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PointsAlongGeometry'] = processing.run('native:pointsalonglines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(21)
        if feedback.isCanceled():
            return {}

        # Extract by location
        alg_params = {
            'INPUT': outputs['PointsAlongGeometry']['OUTPUT'],
            'INTERSECT': outputs['Buffer']['OUTPUT'],
            'PREDICATE': [0],  # intersect
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByLocation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(22)
        if feedback.isCanceled():
            return {}

        # Field calculator
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'Name',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Text (string)
            'FORMULA': "'Ukr gains'",
            'INPUT': outputs['Verschil']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(23)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(24)
        if feedback.isCanceled():
            return {}

        # Delete holes
        alg_params = {
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'MIN_AREA': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteHoles'] = processing.run('native:deleteholes', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(25)
        if feedback.isCanceled():
            return {}

        # Field calculator
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'Name',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Text (string)
            'FORMULA': "'Ru gains'",
            'INPUT': outputs['ExtractByLocation']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(26)
        if feedback.isCanceled():
            return {}

        # Geometry by expression
        alg_params = {
            'EXPRESSION': 'make_polygon(\r\n    close_line(\r\n        make_line(\r\n             array_foreach( \r\n                geometries_to_array(\r\n                    nodes_to_points($geometry)\r\n                ),\r\n                make_point(\r\n                    round(x(@element),7),\r\n                    round(y(@element),7)\r\n                )\r\n            )\r\n        )\r\n    )\r\n)',
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'OUTPUT_GEOMETRY': 0,  # Polygon
            'WITH_M': False,
            'WITH_Z': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GeometryByExpression'] = processing.run('native:geometrybyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(27)
        if feedback.isCanceled():
            return {}

        # Split with lines
        alg_params = {
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'LINES': outputs['FixGeometries']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitWithLines'] = processing.run('native:splitwithlines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(28)
        if feedback.isCanceled():
            return {}

        # Vectorlagen samenvoegen
        alg_params = {
            'CRS': None,
            'LAYERS': [outputs['FieldCalculator']['OUTPUT'],outputs['FieldCalculator']['OUTPUT']],
            'OUTPUT': parameters['PinsAp']
        }
        outputs['VectorlagenSamenvoegen'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['PinsAp'] = outputs['VectorlagenSamenvoegen']['OUTPUT']

        feedback.setCurrentStep(29)
        if feedback.isCanceled():
            return {}

        # Retain fields
        alg_params = {
            'FIELDS': [''],
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RetainFields'] = processing.run('native:retainfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(30)
        if feedback.isCanceled():
            return {}

        # Geometry by expression
        alg_params = {
            'EXPRESSION': 'make_polygon(\r\n    close_line(\r\n        make_line(\r\n             array_foreach( \r\n                geometries_to_array(\r\n                    nodes_to_points($geometry)\r\n                ),\r\n                make_point(\r\n                    round(x(@element),7),\r\n                    round(y(@element),7)\r\n                )\r\n            )\r\n        )\r\n    )\r\n)',
            'INPUT': outputs['SplitWithLines']['OUTPUT'],
            'OUTPUT_GEOMETRY': 0,  # Polygon
            'WITH_M': False,
            'WITH_Z': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GeometryByExpression'] = processing.run('native:geometrybyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(31)
        if feedback.isCanceled():
            return {}

        # Fix geometries
        alg_params = {
            'INPUT': outputs['RetainFields']['OUTPUT'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(32)
        if feedback.isCanceled():
            return {}

        # Extract by expression
        alg_params = {
            'EXPRESSION': '$area > 1',
            'INPUT': outputs['FixGeometries']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(33)
        if feedback.isCanceled():
            return {}

        # Multipart to singleparts
        alg_params = {
            'INPUT': outputs['ExtractByExpression']['OUTPUT'],
            'OUTPUT': parameters['ApOutput']
        }
        outputs['MultipartToSingleparts'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['ApOutput'] = outputs['MultipartToSingleparts']['OUTPUT']
        return results

    def name(self):
        return 'APv2024-10-16'

    def displayName(self):
        return 'APv2024-10-16'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Apv20241016()