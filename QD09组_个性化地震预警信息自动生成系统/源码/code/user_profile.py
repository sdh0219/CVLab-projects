def get_user_profile(identity, age, mobility):
    profiles = []
    if age >= 60:
        profiles.append('老年重点关注人群')
    elif age < 18:
        profiles.append('学生/未成年人群体')
    if identity == '游客':
        profiles.append('外来不熟悉环境人群')
    if identity == '应急人员':
        profiles.append('应急处置工作人员')
    if mobility in ('较弱', '需协助'):
        profiles.append('优先协助转移人群')
    if not profiles:
        profiles.append('普通居民')
    return '、'.join(profiles)


def get_profile_label(identity, age, mobility):
    return get_user_profile(identity, age, mobility)
