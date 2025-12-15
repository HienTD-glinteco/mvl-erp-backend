from django.core.management.commands import makemessages


class Command(makemessages.Command):
    help = "Custom makemessages command that disables fuzzy matching."
    msgmerge_options = makemessages.Command.msgmerge_options + ["--no-fuzzy-matching"]
