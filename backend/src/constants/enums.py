from enum import Enum
class Role(str, Enum): admin='admin'; analyst='analyst'; viewer='viewer'
class SampleStatus(str, Enum): valid='valid'; insufficient='insufficient'; conflicting='conflicting'; excluded='excluded'
class AnalysisStatus(str, Enum): queued='queued'; running='running'; completed='completed'; unexplainable='unexplainable'; failed='failed'
class ReviewStatus(str, Enum): pending='pending'; approved='approved'; rejected='rejected'; blocked='blocked'
class BriefStatus(str, Enum): draft='draft'; issued='issued'
