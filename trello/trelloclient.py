# -*- coding: utf-8 -*-
from __future__ import with_statement, print_function, absolute_import
import json
import requests
from requests_oauthlib import OAuth1
from trello.board import Board
from trello.card import Card
from trello.trellolist import List
from trello.organization import Organization
from trello.member import Member
from trello.webhook import WebHook
from trello.exceptions import *
from trello.label import Label
from trello.star import Star
from trello.util import generate_user_agent

try:
    # PyOpenSSL works around some issues in python ssl modules
    # In particular in python < 2.7.9 and python < 3.2
    # It is not a hard requirement, so it's not listed in requirements.txt
    # More info https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning
    import urllib3.contrib.pyopenssl

    urllib3.contrib.pyopenssl.inject_into_urllib3()
except:
    pass


class TrelloClient(object):
    """ Base class for Trello API access """

    def __init__(self, api_key, api_secret=None, token=None, token_secret=None, http_service=requests, proxies={}):
        """
        Constructor

        :api_key: API key generated at https://trello.com/1/appKey/generate
        :api_secret: the secret component of api_key
        :token: OAuth token generated by the user in
                    trello.util.create_oauth_token
        :token_secret: the OAuth client secret for the given OAuth token
        """

        # client key and secret for oauth1 session
        if token or token_secret:
            self.oauth = OAuth1(client_key=api_key, client_secret=api_secret,
                                resource_owner_key=token, resource_owner_secret=token_secret)
        else:
            self.oauth = None

        self.proxies = proxies
        self.public_only = token is None
        self.api_key = api_key
        self.api_secret = api_secret
        self.resource_owner_key = token
        self.resource_owner_secret = token_secret
        self.http_service = http_service

    def info_for_all_boards(self, actions):
        """
        Use this if you want to retrieve info for all your boards in one swoop
        """
        if self.public_only:
            return None
        else:
            json_obj = self.fetch_json(
                '/members/me/boards/all',
                query_params={'actions': actions})
            self.all_info = json_obj

    def logout(self):
        """Log out of Trello."""
        # TODO: This function.
        raise NotImplementedError()

    def list_boards(self, board_filter="all"):
        """
        Returns all boards for your Trello user

        :return: a list of Python objects representing the Trello boards.
        :rtype: list of Board

        Each board has the following noteworthy attributes:
            - id: the board's identifier
            - name: Name of the board
            - desc: Description of the board (optional - may be missing from the
                    returned JSON)
            - closed: Boolean representing whether this board is closed or not
            - url: URL to the board
        """
        json_obj = self.fetch_json('/members/me/boards/?filter=%s' % board_filter)
        return [Board.from_json(self, json_obj=obj) for obj in json_obj]

    def list_organizations(self):
        """
        Returns all organizations for your Trello user

        :return: a list of Python objects representing the Trello organizations.
        :rtype: list of Organization

        Each organization has the following noteworthy attributes:
            - id: the organization's identifier
            - name: Name of the organization
            - desc: Description of the organization (optional - may be missing from the
                    returned JSON)
            - closed: Boolean representing whether this organization is closed or not
            - url: URL to the organization
        """
        json_obj = self.fetch_json('members/me/organizations')
        return [Organization.from_json(self, obj) for obj in json_obj]

    def get_organization(self, organization_id):
        """Get organization

        :rtype: Organization
        """
        obj = self.fetch_json('/organizations/' + organization_id)

        return Organization.from_json(self, obj)

    def get_board(self, board_id):
        """Get board

        :rtype: Board
        """
        obj = self.fetch_json('/boards/' + board_id)
        return Board.from_json(self, json_obj=obj)

    def add_organization(self, organization_name, description=None, name=None):
        """Create organization
        :param organization_name: Name of the organization to create
        :param description: Optional Description of the organization
        :param name: Unique name of the organization, like a slug
        :rtype: Organization
        """
        post_args = {'displayName': organization_name}
        if description is not None:
            post_args['desc'] = description
        if name is not None:
            post_args['name'] = name

        obj = self.fetch_json('/organizations', http_method='POST', post_args=post_args)
        return Organization.from_json(self, json_obj=obj)

    def add_board(self, board_name, source_board=None, organization_id=None, permission_level='private',
                  default_lists=True):
        """Create board
        :param board_name: Name of the board to create
        :param source_board: Optional Board to copy
        :param permission_level: Permission level, defaults to private
        :rtype: Board
        """
        post_args = {'name': board_name, 'prefs_permissionLevel': permission_level}
        if source_board is not None:
            post_args['idBoardSource'] = source_board.id
        if organization_id is not None:
            post_args['idOrganization'] = organization_id
        if not default_lists:
            post_args['defaultLists'] = False

        obj = self.fetch_json('/boards', http_method='POST',
                              post_args=post_args)
        return Board.from_json(self, json_obj=obj)

    def get_member(self, member_id):
        """Get member

        :rtype: Member
        """
        return Member(self, member_id).fetch()

    def get_card(self, card_id):
        """Get card

        :rtype: Card
        """
        card_json = self.fetch_json('/cards/' + card_id, query_params={'customFieldItems': 'true'})
        list_json = self.fetch_json('/lists/' + card_json['idList'])
        board = self.get_board(card_json['idBoard'])
        return Card.from_json(List.from_json(board, list_json), card_json)

    def get_list(self, list_id):
        """Get list

        :rtype: List
        """
        list_json = self.fetch_json('/lists/' + list_id)
        board = self.get_board(list_json['idBoard'])
        return List.from_json(board, list_json)

    def get_label(self, label_id, board_id):
        """Get Label

        Requires the parent board id the label is on

        :rtype: Label
        """
        board = self.get_board(board_id)
        label_json = self.fetch_json('/labels/' + label_id)
        return Label.from_json(board, label_json)

    def fetch_json(
            self,
            uri_path,
            http_method='GET',
            headers=None,
            query_params=None,
            post_args=None,
            files=None):
        """ Fetch some JSON from Trello """

        # explicit values here to avoid mutable default values
        if headers is None:
            headers = {}
        if query_params is None:
            query_params = {}

        # add user agent header to fetch_json requests
        headers['User-Agent'] = generate_user_agent()

        # if files specified, we don't want any data

        # Per trello api specification payload should not be present on get requests.

        data = None
        
        # if files specified, we don't want any data
        if files is None:
            if post_args is not None:
                data = json.dumps(post_args)

        # set content type and accept headers to handle JSON
        if http_method in ("POST", "PUT", "DELETE") and not files:
            headers['Content-Type'] = 'application/json; charset=utf-8'

        headers['Accept'] = 'application/json'

        # construct the full URL without query parameters
        if uri_path[0] == '/':
            uri_path = uri_path[1:]
        url = 'https://api.trello.com/1/%s' % uri_path

        if self.oauth is None:
            query_params['key'] = self.api_key
            query_params['token'] = self.api_secret

        # perform the HTTP requests, if possible uses OAuth authentication
        response = self.http_service.request(http_method, url, params=query_params,
                                             headers=headers, data=data,
                                             auth=self.oauth, files=files,
                                             proxies=self.proxies)

        if response.status_code == 401:
            raise Unauthorized("%s at %s" % (response.text, url), response)
        if response.status_code != 200:
            raise ResourceUnavailable("%s at %s" % (response.text, url), response)

        return response.json()

    def list_hooks(self, token=None):
        """
        Returns a list of all hooks associated with a specific token. If you don't pass in a token,
        it tries to use the token associated with the TrelloClient object (if it exists)
        """
        token = token or self.resource_owner_key or self.api_secret

        if token is None:
            raise TokenError("You need to pass an auth token in to list hooks.")
        else:
            url = "/tokens/%s/webhooks" % token
            return self._existing_hook_objs(self.fetch_json(url), token)

    def _existing_hook_objs(self, hooks, token):
        """
        Given a list of hook dicts passed from list_hooks, creates
        the hook objects
        """
        all_hooks = []
        for hook in hooks:
            new_hook = WebHook(self, token, hook['id'], hook['description'],
                               hook['idModel'],
                               hook['callbackURL'], hook['active'])
            all_hooks.append(new_hook)
        return all_hooks

    def create_hook(self, callback_url, id_model, desc=None, token=None):
        """
        Creates a new webhook. Returns the WebHook object created.

        There seems to be some sort of bug that makes you unable to create a
        hook using httplib2, so I'm using urllib2 for that instead.
        """
        token = token or self.resource_owner_key or self.api_secret

        if token is None:
            raise TokenError("You need to pass an auth token in to create a hook.")

        url = "https://trello.com/1/tokens/%s/webhooks/" % token
        data = {'callbackURL': callback_url, 'idModel': id_model,
                'description': desc}

        if self.api_key is not None:
            data.update({'key': self.api_key})

        response = self.http_service.post(url, data=data, auth=self.oauth, proxies=self.proxies)

        if response.status_code == 200:
            hook_id = response.json()['id']
            return WebHook(self, token, hook_id, desc, id_model, callback_url, True)
        else:
            raise Exception("Webhook creating failed: %s" % response.text)

    def search(self, query, partial_match=False, models=[],
               board_ids=[], org_ids=[], card_ids=[], cards_limit=10):
        """
        Search trello given a query string.

        :param str query: A query string up to 16K characters
        :param bool partial_match: True means that trello will look for
                content that starts with any of the words in your query.
        :param list models: Comma-separated list of types of objects to search.
                This can be 'actions', 'boards', 'cards', 'members',
                or 'organizations'.  The default is 'all' models.
        :param list board_ids: Comma-separated list of boards to limit search
        :param org_ids: Comma-separated list of organizations to limit search
        :param card_ids: Comma-separated list of cards to limit search
        :param cards_limit: The maximum number of cards to return (up to 1000)

        :return: All objects matching the search criterial.  These can
            be Cards, Boards, Organizations, and Members.  The attributes
            of the objects in the results are minimal; the user must call
            the fetch method on the resulting objects to get a full set
            of attributes populated.
        :rtype list:
        """

        query_params = {'query': query}

        if partial_match:
            query_params['partial'] = 'true'

        # Limit search to one or more object types
        if models:
            query_params['modelTypes'] = models

        # Limit search to a particular subset of objects
        if board_ids:
            query_params['idBoards'] = board_ids
        if org_ids:
            query_params['idOrganizations'] = org_ids
        if card_ids:
            query_params['idCards'] = card_ids
        query_params['cards_limit'] = cards_limit

        # Request result fields required to instantiate class objects
        query_params['board_fields'] = ['name,url,desc,closed']
        query_params['member_fields'] = ['fullName,initials,username']
        query_params['organization_fields'] = ['name,url,desc']

        json_obj = self.fetch_json('/search', query_params=query_params)
        if not json_obj:
            return []

        results = []
        board_cache = {}

        for board_json in json_obj.get('boards', []):
            # Cache board objects
            if board_json['id'] not in board_cache:
                board_cache[board_json['id']] = Board.from_json(
                    self, json_obj=board_json)
            results.append(board_cache[board_json['id']])

        for card_json in json_obj.get('cards', []):
            # Cache board objects
            if card_json['idBoard'] not in board_cache:
                board_cache[card_json['idBoard']] = Board(
                    self, card_json['idBoard'])
                # Fetch the board attributes as the Board object created
                # from the card initially result lacks a URL and name.
                # This Board will be stored in Card.parent
                board_cache[card_json['idBoard']].fetch()
            results.append(Card.from_json(board_cache[card_json['idBoard']],
                                          card_json))

        for member_json in json_obj.get('members', []):
            results.append(Member.from_json(self, member_json))

        for org_json in json_obj.get('organizations', []):
            org = Organization.from_json(self, org_json)
            results.append(org)

        return results

    def list_stars(self):
        """
        Returns all boardStars for your Trello user

        :return: a list of Python objects representing the Trello board stars.
        :rtype: list of Board Stars

        Each board has the following noteworthy attributes:
            - id: the board star's identifier
            - idBoard: ID of starred board
            - pos: position of the board star
        """
        json_obj = self.fetch_json('/members/me/boardStars')
        return [Star.from_json(json_obj=obj) for obj in json_obj]

    def add_star(self, board_id, position="bottom"):
        """Create a star
        :param board_iid: Id of the board to star
        :param position: Optional position of the board star
        :rtype: Star
        """
        post_args = {'idBoard': board_id, 'pos': position}
        obj = self.fetch_json('members/me/boardStars', http_method='POST',
                              post_args=post_args)
        return Star.from_json(json_obj=obj)

    def delete_star(self, star):
        """Deletes a star
        :param board_iid: Id of the board to star
        :param position: Optional position of the board star
        :rtype: Star
        """
        self.fetch_json('members/me/boardStars/{}'.format(star.id), http_method='DELETE')
        return star
