"""
Model exported as python.
Name : SM
Group : 
With QGIS : 33803
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class Sm(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('new_sm', 'New SM', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('old_sm', 'Old SM', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('ukraine_provinces', 'Ukraine provinces', defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('NewLinesSm', 'New Lines SM', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='TEMPORARY_OUTPUT'))
        self.addParameter(QgsProcessingParameterFeatureSink('OldLinesSm', 'Old Lines SM', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='TEMPORARY_OUTPUT'))
        self.addParameter(QgsProcessingParameterFeatureSink('SmOutput', 'SM output', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('PinsSm', 'Pins SM', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='TEMPORARY_OUTPUT'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(26, model_feedback)
        results = {}
        outputs = {}

        # Fix geometries
        alg_params = {
            'INPUT': parameters['ukraine_provinces'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Extract by expression
        alg_params = {
            'EXPRESSION': 'regexp_match("name", \'(?i)^Autonomous Republic of Crimea$\')\n',
            'INPUT': outputs['FixGeometries']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Extract by expression
        alg_params = {
            'EXPRESSION': 'NOT regexp_match("name", \'(?i)\\\\bUkrainian Armed Forces\\\\b\')\n',
            'INPUT': parameters['new_sm'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Retain fields
        alg_params = {
            'FIELDS': ['name'],
            'INPUT': outputs['ExtractByExpression']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RetainFields'] = processing.run('native:retainfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Extract by expression
        alg_params = {
            'EXPRESSION': 'NOT regexp_match("name", \'(?i)\\\\bUkrainian Armed Forces\\\\b\')\n',
            'INPUT': parameters['old_sm'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['RetainFields']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 0.0002,
            'END_CAP_STYLE': 0,  # Round
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Fix geometries
        alg_params = {
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Retain fields
        alg_params = {
            'FIELDS': ['name'],
            'INPUT': outputs['ExtractByExpression']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RetainFields'] = processing.run('native:retainfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # Delete holes
        alg_params = {
            'INPUT': outputs['FixGeometries']['OUTPUT'],
            'MIN_AREA': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteHoles'] = processing.run('native:deleteholes', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': [''],
            'INPUT': outputs['RetainFields']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}

        # Split with lines
        alg_params = {
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'LINES': outputs['FixGeometries']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitWithLines'] = processing.run('native:splitwithlines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'OVERLAY': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': parameters['NewLinesSm']
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['NewLinesSm'] = outputs['Difference']['OUTPUT']

        feedback.setCurrentStep(13)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'OVERLAY': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': parameters['OldLinesSm']
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['OldLinesSm'] = outputs['Difference']['OUTPUT']

        feedback.setCurrentStep(14)
        if feedback.isCanceled():
            return {}

        # Multipart to singleparts
        alg_params = {
            'INPUT': outputs['Difference']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MultipartToSingleparts'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(15)
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

        feedback.setCurrentStep(16)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 0.0002,
            'END_CAP_STYLE': 0,  # Round
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'SEPARATE_DISJOINT': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(17)
        if feedback.isCanceled():
            return {}

        # Difference
        alg_params = {
            'GRID_SIZE': None,
            'INPUT': outputs['ExtractByExpression']['OUTPUT'],
            'OVERLAY': outputs['SplitWithLines']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Difference'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(18)
        if feedback.isCanceled():
            return {}

        # Multipart to singleparts
        alg_params = {
            'INPUT': outputs['Difference']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MultipartToSingleparts'] = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(19)
        if feedback.isCanceled():
            return {}

        # Merge vector layers
        alg_params = {
            'CRS': None,
            'LAYERS': [outputs['Difference']['OUTPUT'],outputs['SplitWithLines']['OUTPUT']],
            'OUTPUT': parameters['SmOutput']
        }
        outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['SmOutput'] = outputs['MergeVectorLayers']['OUTPUT']

        feedback.setCurrentStep(20)
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

        feedback.setCurrentStep(21)
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

        # Extract by location
        alg_params = {
            'INPUT': outputs['PointsAlongGeometry']['OUTPUT'],
            'INTERSECT': outputs['Buffer']['OUTPUT'],
            'PREDICATE': [0],  # intersect
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByLocation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(24)
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

        feedback.setCurrentStep(25)
        if feedback.isCanceled():
            return {}

        # Vectorlagen samenvoegen
        alg_params = {
            'CRS': None,
            'LAYERS': [outputs['FieldCalculator']['OUTPUT'],outputs['FieldCalculator']['OUTPUT']],
            'OUTPUT': parameters['PinsSm']
        }
        outputs['VectorlagenSamenvoegen'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['PinsSm'] = outputs['VectorlagenSamenvoegen']['OUTPUT']
        return results

    def name(self):
        return 'SM'

    def displayName(self):
        return 'SM'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Sm()