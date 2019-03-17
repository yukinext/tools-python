#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 13 07:12:40 2019

@author: yuki_next
"""

import argparse
import datetime
import pathlib
import logging
import os
import sys
import collections
import yaml
import jinja2

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

handler = logging.FileHandler(os.path.splitext(sys.argv[0])[0] + ".log")
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

yaml.add_representer(collections.OrderedDict, lambda dumper, instance: dumper.represent_mapping('tag:yaml.org,2002:map', instance.items()))
yaml.add_representer(type(None), lambda dumper, instance: dumper.represent_scalar('tag:yaml.org,2002:null', "~"))
yaml.add_constructor('tag:yaml.org,2002:map', lambda loader, node: collections.OrderedDict(loader.construct_pairs(node)))

EVERNOTE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
	<ul>
{%- for target_date, dated_messages in messages|dictsort(reverse=true) %}
		<li>
			<div>{{ target_date.strftime('%Y-%m-%d') }}</div>
		</li>
		<ul>
{%- for message in dated_messages|sort(reverse=true, attribute='created') %}
			<li>
				<div>{{ message.created.strftime('%H:%M:%S') }}
{%- set splitted_msgs=message.msg.split(' ') -%}
{%- for splitted_msg in splitted_msgs -%}
{%- if splitted_msg.startswith('#') -%}
&nbsp;<span{{ {'style':'background-color: rgb(255, 250, 165);-evernote-highlight:true;'}|xmlattr }}>{{ splitted_msg }}</span>
{%- else -%}
&nbsp;{{ splitted_msg }}
{%- endif -%}
{%- endfor -%}
                </div>
			</li>
{%- endfor %}
		</ul>
{%- endfor %}
	</ul>
</en-note>
"""

# https://pyyaml.org/wiki/PyYAMLDocumentation#Constructorsrepresentersresvers
class Message(yaml.YAMLObject):
    yaml_tag = "!Message"
    
    def __init__(self, msg, created=datetime.datetime.now()):
        self.msg = msg
        self.created = created
    
    def __repr__(self):
        return "{!s}(msg={!r), created={!r})".format(self.__class__.__name__, self.msg, self.created)
    
def convert_to_evernote_format(messages, template_s=EVERNOTE_TEMPLATE):
    template = jinja2.Template(template_s)
    return template.render(messages=messages)

def proc_insert(args):
    messages = dict() # key: date, value: list() Message
    
    store_filename = args.work_dir / args.store_file
    if store_filename.exists():
        with store_filename.open("r") as fp:
            messages = yaml.load(fp)

    today = datetime.date.today()
    if not today in messages:
        messages[today] = list()
    messages[today].append(Message(" ".join(args.message)))
    
    with store_filename.open("w") as fp:
        yaml.dump(messages, stream=fp, allow_unicode=True, default_flow_style=False)
    
    if args.credential_json_filename.exists():
    # if False:
        from evernote.api.client import EvernoteClient
        import evernote.edam.type.ttypes as Types
        import evernote.edam.notestore.ttypes as NSTypes
        import json
        
        j = None
        with args.credential_json_filename.open("r") as fp:
            j = json.load(fp)
        
        client = EvernoteClient(token=j["evernote_token"])
        note_store = client.get_note_store()
        
        notebook_name = j["notebook_name"]
        notebooks = note_store.listNotebooks()
        target_notebook = None
        for notebook in notebooks:
            if notebook_name == notebook.name:
                target_notebook = notebook
                break
        
        if target_notebook is None:
            logger.info("create notebook: {}".format(notebook_name))
            target_notebook = Types.Notebook()
            target_notebook.name = notebook_name
            target_notebook = note_store.createNotebook(target_notebook)

        target_note = None
        note_title = "memo {:%Y-%m}".format(today)
        
        filter = NSTypes.NoteFilter()
        filter.notebookGuid = target_notebook.guid        
        resultSpec = NSTypes.NotesMetadataResultSpec()
        resultSpec.includeTitle = True
        metalist = note_store.findNotesMetadata(filter, 0, 10, resultSpec)

        for meta_ in metalist.notes:
            if note_title == meta_.title:
                target_note = note_store.getNote(meta_.guid, True, False, False, False)
                break

        if target_note is None:
            logger.info("create note: {}".format(note_title))
            note = Types.Note()
            note.title = note_title
            note.content = convert_to_evernote_format(messages)
            note.notebookGuid = target_notebook.guid
            note_store.createNote(note)
        else:
            logger.info("update note: {}".format(note_title))
            target_note.content = convert_to_evernote_format(messages)
            note_store.updateNote(target_note)
    else:
        logger.info("credential file not found: {}".format(args.credential_json_filename))
        logger.debug(convert_to_evernote_format(messages))
    
def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--work-dir", default=pathlib.Path("~/.mini_memo/").expanduser(), type=pathlib.Path, help="working directory")
    common_parser.add_argument("--store-file", default="memo_{:%Y%m}.yaml".format(datetime.date.today()), help="messages store file name.")
    common_parser.add_argument("--credential-json-filename", default=pathlib.Path(sys.argv[0]).parent / "cred.json", type=pathlib.Path)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    
    parser_insert = subparsers.add_parser("insert", parents=[common_parser], help="insert message", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_insert.add_argument("message", nargs=argparse.REMAINDER)
    parser_insert.set_defaults(handler=proc_insert)
    
    args = parser.parse_args()
    
    args.work_dir.mkdir(parents=True, exist_ok=True)
    
    if hasattr(args, "handler"):
        args.handler(args)

if __name__ == "__main__":
    main()