from collections import OrderedDict
from .. commands.utils import open_location
from LSP.plugin import Session
from LSP.plugin.core.types import Any
import json
import mdpopups


def handle_execute_client(session: Session, params: Any) -> None:
    """Handle the metals/executeClientCommand notification."""

    if not isinstance(params, dict):
        return
    command_name = params.get('command')
    args = params.get('arguments')

    if command_name == "metals-goto-location":
        goto_location(session, args)
    elif command_name == 'metals-show-stacktrace':
        show_stacktrace(session, args)
    elif command_name in {'metals-doctor-run'}:
        run_doctor(session, args)
    else:
        msg = "Unknown command {}".format(command_name)
        session.window.status_message(msg)


def goto_location(session: Session, args: Any) -> None:
    """https://scalameta.org/metals/docs/integrations/new-editor/#goto-location"""

    if isinstance(args, list) and args:
        open_location(session.window, args[0])


def show_stacktrace(session: Session, args: Any) -> None:
    """https://scalameta.org/metals/docs/integrations/new-editor/#show-the-stacktrace-in-the-client"""

    if isinstance(args, list) and args:
        session.window.new_html_sheet('Stacktrace', args[0])


def run_doctor(session: Session, args: Any) -> None:

    def parse_build_target(targets, doctor_version) -> str:
        default_target_labels = OrderedDict([
            ('targetType', 'Target Type'),
            ('compilationStatus', 'Compilation status'),
            ('diagnostics', 'Diagnostics'),
            ('interactive', 'Interactive'),
            ('semanticdb', 'SemanticDB'),
            ('debugging', 'Debugging'),
            ('java', 'Java Support'),
            ('recommendation', 'Recommendation')
        ])

        legacy_target_labels = OrderedDict([
            ('scalaVersion', 'Scala Version'),
            ('diagnostics', 'Diagnostics'),
            ('gotoDefinition', 'Goto Definition'),
            ('completions', 'Completions'),
            ('findReferences', 'Find References')
        ])

        target_labels = default_target_labels if doctor_version > 0 else legacy_target_labels

        if not targets:
            return ''

        lines = []
        markdown = "## Build Targets\n"
        for target in targets:
            lines.append('#### {}'.format(target.get('buildTarget')))
            lines.append('```')

            for field, label in target_labels.items():
                if target.get(field):
                    lines.append('* {0:<20}: {1}'.format(label, target.get(field)))

            lines.append("```")

        markdown += "{}\n\n".format('\n'.join(lines))

        return  markdown

    def parse_explanations(explanations) -> str:
        if explanations:
            markdown = "## Explanations\n"
            for explanation in explanations:
                markdown += '{}\n\n'.format(explanation.get('title'))
                for deep_explanation in explanation.get('explanations'):
                    markdown += '* {}\n'.format(deep_explanation)
                markdown += '\n\n'
            return markdown
        else:
            return ''

    def parse_error_reports(error_reports) -> str:
        if error_reports:
            error_report_labels = OrderedDict(
                [
                    ('timestamp', 'Timestamp'),
                    ('uri', 'URI'),
                    ('buildTarget', 'Build Target'),
                    ('errorReportType', 'Type'),
                ]
            )
            markdown = "## Error Reports\n"

            for error_report in error_reports:
                markdown += "#### {}\n".format(error_report.get("name"))
                lines = []
                lines.append("```")
                for field, label in error_report_labels.items():
                    if error_report.get(field):
                        lines.append(
                            "* {0:<14}: {1}".format(label, error_report.get(field))
                        )
                lines.append("```")
                markdown += "{}\n".format("\n".join(lines))
                markdown += "{}\n\n".format(error_report.get("shortSummary"))
            return markdown
        else:
            return ""

    if isinstance(args, list) and args:
        content = json.loads(args[0])
        doctor_version = 0 if content.get('version') is None else int(content.get('version'))

        header = content.get('header')
        markdown = "# {} \n\n".format(content.get('title'))

        if doctor_version >= 4:
            header_fields = [
                'buildTargetDescription',
                'serverInfo',
                'jdkInfo'
            ]

            folder_header_fields = OrderedDict([
                ('buildTool', 'Build tool'),
                ('buildServer', 'Build Server'),
                ('importBuildStatus', 'Import Build Status')
            ])

            for field in header_fields:
                value = header.get(field)
                if value:
                    markdown += "{} \n\n".format(value)

            folders = content.get('folders')
            for folder in folders:
                header = folder.get('header')
                for field, label in folder_header_fields.items():
                    if header.get(field):
                        markdown += "{}: {} \n\n".format(label, header.get(field))

                markdown += parse_build_target(folder.get('targets'), doctor_version)
                markdown += parse_explanations(folder.get('explanations'))
                markdown += parse_error_reports(folder.get('errorReports'))
        else:
            messages = content.get('messages')
            targets = content.get('targets')
            explanations = content.get('explanations')

            if doctor_version == 3:
                fields = [
                  'buildTool',
                  'buildServer',
                  'importBuildStatus',
                  'jdkInfo',
                  'serverInfo'
                ]

                for field in fields:
                  if header.get(field):
                    markdown += "{} \n\n".format(header.get(field))

                markdown += "{} \n\n".format(header.get('buildTargetDescription'))
            else:
                markdown += "{} \n\n".format(content.get('headerText'))

            if messages:
                for message in messages:
                    markdown += "### {} \n".format(message.get('title'))
                    for recommendation in message.get('recommendations'):
                        markdown += '* {}\n'.format(recommendation)
                    markdown += '\n\n'
            elif targets:
                markdown += parse_build_target(targets, doctor_version)
                markdown += parse_explanations(explanations)

        custom_css = """
        .metals-doctor { padding: 1.5rem }
        .metals-doctor h1, .metals-doctor h2 { text-decoration: underline }
        .metals-doctor h2, .metals-doctor h3, .metals-doctor h4, .metals-doctor p, .metals-doctor ul { margin-top: 1rem }
        """

        mdpopups.new_html_sheet(session.window, "Metals Doctor", markdown, True, css=custom_css, wrapper_class="metals-doctor")
