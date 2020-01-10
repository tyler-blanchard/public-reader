import logging
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
import utils

import difflib

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome, what book would you like me to read?"
        
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["state"] = 'NOT_STARTED'

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class OpenBookIntentHandler(AbstractRequestHandler):
    """Handler for Open Book Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        correct_intent_name = ask_utils.is_intent_name("OpenBookIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        not_started = False
        if session_attr["state"] == 'NOT_STARTED':
            not_started = True
        
        return correct_intent_name and not_started

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        
        book_title = handler_input.request_envelope.request.intent.slots["title"].value
        
        results = utils.query(book_title)
        
        result_length = len(results)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        # no results
        if result_length == 0:
            speak_output = 'Sorry, I couldn\'t find that. Try saying another title.'
        # one result
        elif result_length == 1:
            session_attr["state"] = "SEARCH_RESULTS"
            speak_output = 'I have found one title: {} by {}. Would you like me to read it to you?'.format(results[0]['title'], results[0]['author'])
            session_attr["book"] = results[0]
        else:
            session_attr["state"] = "SEARCH_RESULTS"
            session_attr["search_results"] = results
            books = [ book['title'] + ' by ' + book['author'] for book in results ]
            books_string = ' <break time="0.5s"/> , '.join(books)
            speak_output = 'I have found {} results, which would you like? {}'.format(result_length, books_string)

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class ChooseBookIntentHandler(AbstractRequestHandler):
    """ Handler for choosing book from results """
    def can_handle(self, handler_input):
        
        correct_intent_name = ask_utils.is_intent_name("OpenBookIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        search_results = False
        if session_attr["state"] == 'SEARCH_RESULTS':
            search_results = True
            
        book_in_session = False
        if 'book' in session_attr:
            book_in_session = True
        
        return correct_intent_name and search_results and not book_in_session
        
    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        book_title = handler_input.request_envelope.request.intent.slots["title"].value
        results =session_attr['search_results']
        titles = [ result['title'] for result in results ]

        match = difflib.get_close_matches(book_title, titles)[0]
        
        matched_book = results[0]
        
        
        for result in results:
            if result['title'] == match:
                matched_book = result
                break
        
        session_attr["book"] = matched_book
        
        speak_output = '{} by {}. Would you like me to read it to you?'.format(matched_book['title'], matched_book['author'])
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_should_end_session(False)
                .response
        )

class ChooseChapterIntentHandler(AbstractRequestHandler):
    """ Handler for choosing book from results """
    def can_handle(self, handler_input):
        
        correct_intent_name = ask_utils.is_intent_name("OpenBookIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        book_has_started = False
        if session_attr["state"] == 'STARTED':
            book_has_started = True
        
        return correct_intent_name and book_has_started
        
    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        title = handler_input.request_envelope.request.intent.slots["title"].value
        
        epub = utils.open_zipped_epub()
        
        chapter = epub.read_by_chapter_title(title)
        
        response = utils.read_chapter(handler_input, chapter)
        
        return response

class StartBookIntentHandler(AbstractRequestHandler):
    """ Handler for starting the book """
    def can_handle(self, handler_input):
        
        correct_intent_name = ask_utils.is_intent_name("StartBookIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
            
        book_has_started = False
        if session_attr["state"] == 'STARTED':
            book_has_started = True
            
        
        return correct_intent_name and book_has_started
        
    def handle(self, handler_input):
        
        epub = utils.open_zipped_epub()
        
        chapter = epub.begin()
        
        response = utils.read_chapter(handler_input, chapter)
        
        return response


class ConfirmBookIntentHandler(AbstractRequestHandler):
    """ Handler for confirming book """
    def can_handle(self, handler_input):
        
        correct_intent_name = ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        
        search_has_results = False
        if "book" in session_attr:
            search_has_results = True
            
        book_has_started = True
        if session_attr["state"] != "STARTED":
            book_has_started = False
            
        
        return correct_intent_name and search_has_results and not book_has_started
        
    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        session_attr["state"] = "STARTED"
        
        session_attr = handler_input.attributes_manager.session_attributes
        book = session_attr["book"]
        link = book["titleLink"]
        
        epub = utils.open_book(link)
        
        toc = epub.get_chapter_titles()
        toc_string = ', <break time="0.5s"/>'.join(toc)
        
        speak_output = 'Here are the chapters. Where would you like me to start? ' + toc_string

        reprompt = "Say 'beginning' and I will read from the start."
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(reprompt)
                .set_should_end_session(False)
                .response
        )


class NextPageIntentHandler(AbstractRequestHandler):
    """ Handler for the next page intent """
    def can_handle(self, handler_input):
        
        correct_intent_name = ask_utils.is_intent_name("AMAZON.NextIntent")(handler_input)
        
        started = False
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        if session_attr["state"] == "STARTED":
            started = True
            
        return correct_intent_name and started
        
    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        bookmark = session_attr['bookmark']
        file = bookmark['file']
        section = bookmark['section']
        
        epub = utils.open_zipped_epub()
        chapter = epub.next(file, section)
        response = utils.read_chapter(handler_input, chapter)
        
        return response

    
class PreviousPageIntentHandler(AbstractRequestHandler):
    """ Handler for the previous page intent """
    def can_handle(self, handler_input):
        correct_intent_name = ask_utils.is_intent_name("AMAZON.PreviousIntent")(handler_input)
        
        started = False
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        if session_attr["state"] == "STARTED":
            started = True
            
        return correct_intent_name and started
        
    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        bookmark = session_attr['bookmark']
        file = bookmark['file']
        section = bookmark['section']
        
        epub = utils.open_zipped_epub()
        chapter = epub.previous(file, section)
        
        response = utils.read_chapter(handler_input, chapter)
        
        return response
    

class ReadChapterIntentHandler(AbstractRequestHandler):
    
    def can_handle(self, handler_input):
        correct_intent_name = ask_utils.is_intent_name("ReadChapterIntent")(handler_input)
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        started = False
        if session_attr["state"] == "STARTED":
            started = True
            
        return correct_intent_name and started
        
    def handle(self, handler_input):
        
        epub = utils.open_zipped_epub()
        
        slots = handler_input.request_envelope.request.intent.slots
        chapter_slot = slots["chapter"].value
        part_slot = slots["part"].value
        
        chapter = epub.read(chapter=chapter_slot, part=part_slot)
        
        response = utils.read_chapter(handler_input, chapter)
        
        return response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        
        session_attr = handler_input.attributes_manager.session_attributes
        
        state = session_attr["state"]
        
        if state == "NOT_STARTED" or state == "SEARCH_RESULTS":
            speak_output = "Tell me what to read."
        elif state == "STARTED":
            epub = utils.open_zipped_epub()
            
            toc = epub.get_chapter_titles()
            toc_string = ', <break time="0.5s"/>'.join(toc)
            
            speak_output = "Tell me what to read. You can navigate within the book by saying 'previous' or 'next'. These are the chapters: " + toc_string

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .set_should_end_session(False)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel, Stop, and No Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.NoIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        session_attr = handler_input.attributes_manager.session_attributes
        
        state = session_attr["state"]
        
        speak_output = 'Goodbye!'
        reprompt = ''
        should_end_session = True
        
        if state == 'SEARCH_RESULTS':
            speak_output = 'What book would you like me to read?'
            reprompt = speak_output
            should_end_session = False
            
            session_attr['state'] = 'NOT_STARTED'
            session_attr.pop('search_results', None)
            session_attr.pop('book', None)
            
        elif state == 'STARTED':
            speak_output = 'Which chapter should I read.'
            reprompt = speak_output
            should_end_session = False

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(reprompt)
                .set_should_end_session(should_end_session)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


# class IntentReflectorHandler(AbstractRequestHandler):
#     """The intent reflector is used for interaction model testing and debugging.
#     It will simply repeat the intent the user said. You can create custom handlers
#     for your intents by defining them above, then also adding them to the request
#     handler chain below.
#     """
#     def can_handle(self, handler_input):
#         # type: (HandlerInput) -> bool
#         return ask_utils.is_request_type("IntentRequest")(handler_input)

#     def handle(self, handler_input):
#         # type: (HandlerInput) -> Response
#         intent_name = ask_utils.get_intent_name(handler_input)
#         speak_output = "You just triggered " + intent_name + "."

#         return (
#             handler_input.response_builder
#                 .speak(speak_output)
#                 # .ask("add a reprompt if you want to keep the session open for the user to respond")
#                 .response
#         )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .set_should_end_session(False)
                .response
        )

### routing

sb = SkillBuilder()

# launch
sb.add_request_handler(LaunchRequestHandler())

# custom 
sb.add_request_handler(StartBookIntentHandler())
sb.add_request_handler(OpenBookIntentHandler())
sb.add_request_handler(ChooseBookIntentHandler())
sb.add_request_handler(ChooseChapterIntentHandler())
sb.add_request_handler(ConfirmBookIntentHandler())
sb.add_request_handler(NextPageIntentHandler())
sb.add_request_handler(PreviousPageIntentHandler())
sb.add_request_handler(ReadChapterIntentHandler())

# built in 
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
#sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

# error handling
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()