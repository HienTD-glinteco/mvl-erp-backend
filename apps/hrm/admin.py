from django.contrib import admin

from .models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    OrganizationChart,
    Position,
    RecruitmentChannel,
    RecruitmentSource,
)

admin.site.register(Block)
admin.site.register(Branch)
admin.site.register(Department)
admin.site.register(OrganizationChart)
admin.site.register(Position)
admin.site.register(RecruitmentChannel)
admin.site.register(RecruitmentSource)
admin.site.register(Employee)
admin.site.register(JobDescription)
