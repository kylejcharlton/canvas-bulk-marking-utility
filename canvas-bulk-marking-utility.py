#!/usr/bin/env python3
import argparse
import os
import sys
import datetime
import time
import requests


# Initialize some variables:
start_date = datetime.datetime(1970, 1, 1).isoformat()


def generate_auth_header(token: str):
    return {'Authorization': 'Bearer ' + token}

# Necessary to list all announcements
# Work through Canvas' pagination model if the relevant links exist
def get_paginated_list(result: requests.models.Response, token: str) -> list:
    """
    Easily handle pagination with Canvas API requests
    """

    print('\tRetrieving all entries...')
    auth = generate_auth_header(token)
    items_list = result.json()

    while True:
        try:
            result.headers['Link']

            # Handle pagination links
            pagination_links = result.headers['Link'].split(',')

            pagination_urls = {}
            for link in pagination_links:
                url, label = link.split(';')
                label = label.split('=')[-1].replace('"', '')
                url = url.replace('<', '').replace('>', '')
                pagination_urls.update({label: url})

            # Now try to get the next page
            print('\tGetting next page...')
            result = requests.get(pagination_urls['next'], headers=auth)
            items_list.extend(result.json())

        except KeyError:
            print('\tReached end of paginated list')
            break

    return items_list


def mark_all_discussions_read(domain: str, token: str, course_id: int) -> None:
    auth = generate_auth_header(token)
    url = domain + '/api/v1/courses/' + str(course_id) + '/discussion_topics'
    discussions_response = requests.get(url, headers=auth, params={"per_page": 10000})

    if discussions_response.status_code != 200:
        print(f"Cannot access course {course_id} -- are you authorized to view this course?")
        return

    discussions_list = get_paginated_list(discussions_response, token)
    for topic in discussions_list:
        try:
            topic_id = topic['id']
            if topic['read_state'] == 'unread':
                requests.put(domain + '/api/v1/courses/' + str(course_id) + '/discussion_topics/' + str(topic_id) + '/read_all.json', headers={**auth, **{"Content-Length": "0"}}, params={"per_page": 10000})
                time.sleep(1)
        except TypeError:
            print(f"Couldn't get info for topic {topic}. Skipping.")


def mark_old_todos_complete(domain: str, token: str) -> None:
    print("Marking old TODOs...")
    auth = generate_auth_header(token)
    end_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    activities_response = requests.get(domain + '/api/v1/planner/items', headers=auth, params={'start_date': start_date, 'end_date': end_date, 'per_page': 10000})
    activities = get_paginated_list(activities_response, token)
    for item in activities:
        if item['planner_override'] == None:
            print("\tMarking item: " + item['plannable']['title'] + " (" + item['plannable_date'][:10] + ")")
            requests.post(domain + '/api/v1/planner/overrides', headers=auth, params={'plannable_type': item['plannable_type'], 'plannable_id': item['plannable_id'], 'marked_complete': True})
            time.sleep(1)
        elif item['planner_override']['marked_complete'] == False:
            print("\tMarking item: " + item['plannable']['title'] + " (" + item['plannable_date'][:10] + ")")
            requests.put(domain + '/api/v1/planner/overrides/' + str(item['planner_override']['id']), headers=auth, params={'marked_complete': 'true'})
            time.sleep(1)
    print("\tDone.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('-D', '--domain', required=True, help='Your institution\'s domain for Canvas (e.g. https://utah.instructure.com)')
    parser.add_argument('-T', '--token', required=True, help='Your Canvas LMS Token')
    parser.add_argument('-a', '--announcements', action='store_true', help='Mark old announcements as read')
    parser.add_argument('-d', '--discussions', action='store_true', help='Mark old discussions as read')
    parser.add_argument('-t', '--todos', action='store_true', help='Mark old TODOs as complete')
    parser.add_argument('-u', '--unread', action='store_true', help='Mark old activities as read')
    parser.add_argument('-A', '--all', action='store_true', help='Enable all options')
    args = parser.parse_args()

    token = args.token
    domain = args.domain

    if args.all or args.todos:
        mark_old_todos_complete(domain, token)

    if args.all or args.discussions or args.announcements:
        print("Retrieving course list...")
        auth = generate_auth_header(token)
        courses_response = requests.get(domain + '/api/v1/courses', headers=auth, params={"per_page": 10000})

        if courses_response.status_code != 200:
            print("Unable to access courses. Verify both the domain and token are correct.")
            return 1

        courses_list = get_paginated_list(courses_response, token)
        for course in courses_list:
            try:
                course_id = course['id']
            except TypeError:
                print(f"Couldn't get info for course {course}. Skipping.")
                continue

            try:
                print(f"Marking discussions for course {course_id} ({course['name']})")
            except KeyError:
                print(f"Marking discussions for course {course_id}")

            mark_all_discussions_read(domain, token, course_id)

    return 0


if __name__ == '__main__':
    sys.exit(main())
