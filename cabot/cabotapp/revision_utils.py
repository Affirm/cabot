import reversion
from reversion.models import Version
from django.utils.html import escape


def get_revisions(obj, n_revisions=3):
    """
    Get the last N diffs for an object that is tracked by django-reversion, as (v1, v2) human-readable string tuples.
    Foreign key fields will show their *current* string representation.
    Deleted foreign key fields will show as 'deleted' or 'deleted: <last known object repr>'.
    Diff strings may be HTML formatted. Any user-supplied values are first HTML-escaped.
    :param obj: object to get a diff for
    :param n_revisions: maximum number of revisions to get (default 3)
    :return: list of (revision, {field: (v1_str, v2_str), ...}) tuples
    """
    # type: (Any, int) -> List[Tuple[reversion.models.Revision, Dict[str, Tuple[str, str]]]]
    recent_versions = Version.objects.get_for_object(obj)[:n_revisions+1]

    # grab fields on the object's model
    fields = [f for f in obj._meta.fields]

    # also grab many-to-many fields
    concrete_model = obj._meta.concrete_model
    fields += concrete_model._meta.many_to_many

    revisions = []
    for i in range(len(recent_versions) - 1):
        cur = recent_versions[i]
        prev = recent_versions[i+1]
        changes = compare_versions(fields, prev, cur)
        if len(changes) > 0:
            revisions.append((cur.revision, changes))

    return revisions


def compare_versions(fields, v1, v2):
    """
    Return HTML-formatted diffs for a list of fields.
    :param fields: list of Django field objects
    :param v1: reversion.Version for the previous version of the object
    :param v2: reversion.Version for the new version of the object
    :return: dict of {'field_name': (v1_value_str, v2_value_str), ...}
    """
    # type: (List[Field], reversion.models.Version, reversion.models.Version) -> Dict[str, Tuple[str, str]]

    class MutedStr:
        def __init__(self, s):
            self.msg = s

        def __str__(self):
            return '<span class="text-muted">{}</span>'.format(escape(self.msg))

    def obj_to_str_escaped(obj):
        # type: (Any) -> str
        """
        Converts an object to an HTML-escaped string (but note the return value may contain HTML for styling special
        values like None).
        """

        if obj is None or obj == '':
            return str(MutedStr('none'))
        elif isinstance(obj, list):
            return '[' + ', '.join([obj_to_str_escaped(o) for o in obj]) + ']'
        elif isinstance(obj, MutedStr):
            return str(obj)  # already escaped

        try:
            return escape(str(obj))
        except:
            try:
                return escape(repr(obj))
            except:
                return str(MutedStr('<error: could not build string>'))

    def field_to_str_escaped(field, version):
        """
        Converts data from django-reversion to a nice string, based on the given django fields. Most importantly,
        handles looking up foreign keys and many-to-many relationships if they still exist in the DB.
        :param field: list of django field objects
        :param version: django-reversion Version object
        :return: human-readable string representing field of version; may contain HTML
        """
        value = version.field_dict.get(field.name)
        if field.get_internal_type() == 'ManyToManyField':
            ids = [int(v) for v in value]
            related_model = field.rel.to

            related_objs = []
            for related in related_model.objects.filter(id__in=ids):
                related_objs.append(related)
                ids.remove(related.pk)

            # if it's not in the live set, try and find it in a "deleted" revision
            for version in Version.objects.get_deleted(related_model).filter(object_id__in=ids):
                # we use the object repr here because version.object is none for some reason
                related_objs.append(MutedStr('deleted: {}'.format(version.object_repr)))
                ids.remove(version.object_id_int)

            # alternatively pull related objects from same revision
            # value = version.revision.version_set.filter(
            #     content_type=ContentType.objects.get_for_model(related_model),
            #     object_id_int__in=ids
            # )

            # for anything we couldn't find, just give a fixed 'deleted' string
            value = related_objs + [MutedStr('deleted') for _ in ids]
        elif field.get_internal_type() == 'ForeignKey':
            try:
                value = value.rel.get()
            except:
                value = MutedStr('deleted')

        return obj_to_str_escaped(value)

    changes = {}
    for field in fields:
        v1_value = v1.field_dict.get(field.name)
        v2_value = v2.field_dict.get(field.name)
        if v1_value != v2_value:
            v1_str = field_to_str_escaped(field, v1)
            v2_str = field_to_str_escaped(field, v2)
            changes[field.name] = (v1_str, v2_str)

    return changes
