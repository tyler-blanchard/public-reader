import zipfile
from lxml import etree
import re
import io
import math
import difflib

class Epub:

    # constants
    
    # alexa max character output is 8000
    __CHUNK_SIZE = 7500
    __CHAPTER_PATH = 'epub/text/'

    # initialization
    def __init__(self, zipped_epub: zipfile.ZipFile):
        self.__zipped_epub = zipped_epub
        self.__toc = self.__get_toc()
        self.__has_parts = self.__has_parts()
    
    ### private functions
    
    def __get_toc(self):
        """ Returns epub toc
            
        :return: epub toc
        """

        # acceptable patterns in expected epub file
        chapter_patterns = [
            self.__CHAPTER_PATH + "preface*",
            self.__CHAPTER_PATH + "chapter*",
            self.__CHAPTER_PATH + "act*",
            self.__CHAPTER_PATH + "epilogue*"
        ]

        
        toc_files = []    
        
        # iterate through patterns to find matching files in epub
        # preface -> chapters -> epilogue
        for chapter_pattern in chapter_patterns:

            pattern = re.compile(chapter_pattern)

            group = []

            # append to a list 
            for file_name in self.__zipped_epub.namelist():
                if pattern.match(file_name):
                    group.append(file_name)

            # sort list and append to parent list
            # ensures order
            def atoi(text):
                return int(text) if text.isdigit() else text
            
            def natural_keys(text):
                '''
                alist.sort(key=natural_keys) sorts in human order
                http://nedbatchelder.com/blog/200712/human_sorting.html
                (See Toothy's implementation in the comments)
                '''
                return [ atoi(c) for c in re.split(r'(\d+)', text) ]
            
            group.sort(key=natural_keys)
              
            
            # now find attributing file names
            for file_name in group:
                
                xml = self.__zipped_epub.read(file_name)
                
                title = self.__get_chapter_title(file_name, xml)

                chapter = {
                    'file': file_name,
                    'title': title
                }
                
                toc_files.append(chapter)

        return toc_files

    # parses chapter text
    def __get_chapter_text(self, xml):
        """ Parses xml to obtain text

        :param xml: string representation of an xml
        :return: string containing xml text
        """
        
        ns = {
            'n': 'http://www.w3.org/1999/xhtml'
        }


        tree = etree.fromstring(xml, parser=etree.XMLParser())
        body_element = tree.xpath('n:body', namespaces=ns)[0]

        encoding = 'utf-8'
        text = etree.tostring(body_element, encoding=encoding).decode(encoding, 'ignore')

        buf = io.StringIO(text)
        res = ''


        for line in buf:
            stripped_line = re.sub('<[^<]+?>', '', line).strip()
            if stripped_line:
                res += ' <break time="0.5s"/> ' + stripped_line

        if len(res) != 0:
            
            sections = []
            
            
            # break into chunks for alexas limit
            section = ''
            delimeter = '. '
            for sentence in res.split(delimeter):
                
                # when delimeter doesn't split correctly, defaults to splitting into chunks based on letter count
                if len(sentence) > self.__CHUNK_SIZE:
                    chunks, chunk_size = len(res), self.__CHUNK_SIZE
                    res = [ res[i:i+chunk_size] for i in range(0, chunks, chunk_size) ]
                    
                    return res
                
                if len(sentence) + len(section) <= self.__CHUNK_SIZE:
                    section += sentence + delimeter
                else:
                    sections.append(section)
                    section = ''
            
            if section not in sections:
                sections.append(section)

            return sections
        else:
            return []
            
    
    def __get_chapter_title(self, file: str, xml: str):
        """ Parses xml to obtain title for the chapter

        :param xml: string representation of xml
        :return: chapter title
        """

        ns = {
            'n': 'http://www.w3.org/1999/xhtml'
        }
        
        tree = etree.fromstring(xml, parser=etree.XMLParser())
        title = tree.xpath('n:head/n:title/text()', namespaces=ns)[0]
        
        if self.__has_parts and 'chapter' in title.lower() and 'part' not in title.lower():
            
            integers = [ int(s) for s in file.split('-') if s.isdigit()]
            
            if len(integers) > 0:
                part = integers[0]
                        
                title = 'Part {} {}'.format(str(part), title)
            
        return title


    def __has_parts(self):
        """ Determines whether epub is in parts or just chapters
    
        :return: boolean true if epub is in parts
        """
        
        pattern = re.compile('epub\/text\/chapter-.*-.*\.xhtml')

        for chapter in self.__toc:
            
            file = chapter['file']

            if pattern.match(file):
                return True

        return False

    def __build_file_name(self, chapter, part=None):
        """ Creates a chapter file name 

        :param chapter: string
        :parm part: string
        :return: File name with chapter and parts
        """

        if self.__has_parts:
            
            if part == None:
                part = 1
            
            file = self.__CHAPTER_PATH + 'chapter-{}-{}.xhtml'.format(part, chapter)  
        else:
            file = self.__CHAPTER_PATH + 'chapter-{}.xhtml'.format(chapter)

        return file

    def __read_file(self, file, section=0):
        """ Reads a file in epub

        :param file: string of file name
        :param section: section of file
        :return: chapter information from file
        """

        xml = self.__zipped_epub.read(file)
            
        text = self.__get_chapter_text(xml)

        res = {
            'file': file,
            'section': section,
            'text': text[section]
        }

        if section == 0:
            res['title'] = self.__get_chapter_title(file, xml)
        
        return res

    def __get_file_index(self, file):
        """ Determines index of file in epub list

        :param file: string of file name
        :return: integer of file index in self.__toc
        """
        
        index = 0
        
        files = [ chapter['file'] for chapter in self.__toc ]
        
        if file not in files:
            return -1
        else:
            return files.index(file)

    ### public functions

    def begin(self):
        """ Start reading chapter from the beginning of the book

        :return: chapter information from beginning of book
        """
        
        first_chapter = self.__toc[0]
        
        file = first_chapter['file']

        xml = self.__zipped_epub.read(file)
        title = self.__get_chapter_title(file, xml)
        text = self.__get_chapter_text(xml)

        section = 0

        res = {
            'file': file,
            'section': section,
            'title': title,
            'text': text[section]
        }
        
        return res
        
    def read(self, chapter, part=None, section=0):
        """ Reads desired chapter, part, and section

        :param chapter: integer of chapter
        :part part: integer of part
        :param section: integer of section
        :return: chapter information
        """

        file = self.__build_file_name(chapter, part=part)
        
        files = [ chapter['file'] for chapter in self.__toc ]

        return self.__read_file(file, section=section)
        
        
    def read_by_chapter_title(self, title):
        """ Finds closest title and reads it

        :param title: desired title of book
        :return: chapter information
        """
        
        titles = self.get_chapter_titles()
        
        matches = difflib.get_close_matches(title, titles)
        
        if len(matches) > 0:
            match = matches[0]
            
            for chapter in self.__toc:
                if chapter['title'] == match:
                    file = chapter['file']
                    
                    return self.__read_file(file, section=0)
        
        return

    def next(self, file, section=0):
        """ Finds next section / chapter of book

        :param file: current file that was read
        :param section: current section that was read
        :return: chapter information
        """
        
        try:
            next_section = self.__read_file(file, section + 1)

            return next_section
        except: 
            
            index = self.__get_file_index(file)
            
            if index < 0 or index >= len(self.__toc) - 1:
                return

            next_chapter_file = self.__toc[index + 1]['file']
            next_chapter = self.__read_file(next_chapter_file)

            return next_chapter


    def previous(self, file, section = 0):
        """ Finds previous section / chapter of book

        :param file: current file that was read
        :param section: current section that was read
        :return: chapter information
        """        

        if section == 0:
            
            index = self.__get_file_index(file)
            
            if index <= 0:
                return
            
            previous_chapter_file = self.__toc[index - 1]['file']
            previous_chapter = self.__read_file(previous_chapter_file)

            return previous_chapter
        else:
            previous_section = self.__read_file(file, section - 1)

            return previous_section
            
    def get_chapter_titles(self):
        """ List of all chapter titles in book

        :return: array of all chapter titles
        """
        
        titles = [ chapter['title'] for chapter in self.__toc ]
            
        return titles

