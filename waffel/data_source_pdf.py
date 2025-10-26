#!/usr/bin/env python3

import PyPDF2
import re
import logging
import requests
from functools import lru_cache
from .data_source import DataSource

logger = logging.getLogger(__name__)

class PDFDataSource(DataSource):
    """PDF-based data source with all PDF parsing logic"""
    
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
    
    def extract_workload_properties(self):
        """Extract workload properties from PDF"""
        
        with open(self.pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            workload_props = {}
            
            # Extract text from first few pages
            for page in reader.pages[:5]:
                text = page.extract_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                # Find workload properties section
                for i, line in enumerate(lines):
                    if line == 'Workload properties':
                        # Process the properties that follow
                        j = i + 1
                        current_property = None
                        
                        while j < len(lines):
                            line = lines[j]
                            
                            # Skip copyright and page info
                            if '©' in line or 'Page ' in line:
                                break
                            
                            # Property labels
                            if line in ['Workload name', 'ARN', 'Description', 'Review owner', 
                                       'Industry type', 'Industry', 'Environment', 'AWS Regions', 
                                       'Non-AWS regions', 'Account IDs', 'Architectural design']:
                                current_property = line
                            elif current_property and line != '-':
                                # Handle multi-line values
                                if current_property == 'ARN':
                                    # Combine ARN parts
                                    arn_parts = [line]
                                    k = j + 1
                                    while k < len(lines) and not lines[k] in ['Description', 'Review owner']:
                                        if not ('©' in lines[k] or 'Page ' in lines[k]):
                                            arn_parts.append(lines[k])
                                        k += 1
                                    workload_props[current_property] = ''.join(arn_parts)
                                    j = k - 1
                                elif current_property == 'Description':
                                    # Combine description parts
                                    desc_parts = [line]
                                    k = j + 1
                                    while k < len(lines) and not lines[k] in ['Review owner', 'Industry type']:
                                        if not ('©' in lines[k] or 'Page ' in lines[k]):
                                            desc_parts.append(lines[k])
                                        k += 1
                                    workload_props[current_property] = ' '.join(desc_parts)
                                    j = k - 1
                                else:
                                    workload_props[current_property] = line
                                current_property = None
                            elif current_property and line == '-':
                                # Handle dash values (empty fields)
                                if current_property == 'Non-AWS regions':
                                    workload_props[current_property] = '-'
                                elif current_property == 'Account IDs':
                                    workload_props[current_property] = '-'
                                current_property = None
                            
                            j += 1
                        
                        # Add missing fields with default values if not found
                        if 'Account IDs' not in workload_props or workload_props.get('Account IDs') == '-':
                            # Try to extract from ARN
                            if 'ARN' in workload_props:
                                arn_match = re.search(r':(\d{12}):', workload_props['ARN'])
                                if arn_match:
                                    workload_props['Account IDs'] = arn_match.group(1)
                        
                        if 'Date' not in workload_props:
                            # Look for date in architectural design or elsewhere
                            for prop, value in workload_props.items():
                                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(value))
                                if date_match:
                                    workload_props['Date'] = date_match.group(1)
                                    # Clean the original property
                                    workload_props[prop] = re.sub(r'\d{1,2}/\d{1,2}/\d{4}', '', str(value)).strip()
                                    if not workload_props[prop]:
                                        workload_props[prop] = 'Application'
                                    break
                        
                        return workload_props
            
            return workload_props
    
    def extract_hyperlinks_from_pdf(self):
        """Extract hyperlinks from PDF annotations by page"""
        
        hyperlinks_by_page = {}
        with open(self.pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(reader.pages, 1):
                hyperlinks_by_page[page_num] = []
                try:
                    if '/Annots' in page:
                        annotations = page['/Annots']
                        for annot_ref in annotations:
                            try:
                                annot = annot_ref.get_object()
                                if '/A' in annot and '/URI' in annot['/A']:
                                    uri = str(annot['/A']['/URI'])
                                    hyperlinks_by_page[page_num].append(uri)
                            except Exception:
                                continue
                except Exception as exc:
                    logger.exception(exc)
                    continue
        
        return hyperlinks_by_page
    
    @lru_cache(maxsize=100)
    def get_wa_framework_urls(self, base_url="https://docs.aws.amazon.com/wellarchitected/2025-02-25/framework"):
        """Fetch all Well-Architected Framework URLs dynamically with caching"""
        try:
            toc = requests.get(f'{base_url}/toc-contents.json').json()
            all_pages = []
            def _process(toc):
                for t in toc:
                    if 'contents' in t:
                        _process(t['contents'])
                    all_pages.append((t['title'], f'{base_url}/{t["href"]}'))
            _process(toc['contents'])
            return all_pages
        except:
            return []
    
    def match_improvement_item_to_url(self, item_text, available_urls):
        """Match improvement item text directly against TOC titles"""
        
        base_urls = set([
            url.rsplit('/', 1)[0]
            for url in available_urls
            if 'https://docs.aws.amazon.com/wellarchitected/' in url
        ])
        
        # Get all TOC pages (cached)
        wa_pages = sum([self.get_wa_framework_urls(base_url) for base_url in base_urls], [])
        if not wa_pages:
            logger.warning(f'Cannot read urls. No match for {item_text}')
            return ''
        
        # Direct text matching against TOC titles
        item_lower = item_text.lower().replace('-',' ').replace(' ','').replace('events', 'alerts')
        
        # First pass: exact substring matching
        for title, url in wa_pages:
            title_lower = title.lower().replace('-',' ').replace(' ','').replace('events', 'alerts')
            # Check if improvement item text contains the TOC title
            if item_lower in title_lower:
                return url
        
        logger.warning(f'Failed to match {item_text}')
        return ''
    
    def extract_improvement_plan_with_smart_urls(self):
        """Extract Well-Architected data with smart URL matching"""
        
        # First extract all hyperlinks by page
        hyperlinks_by_page = self.extract_hyperlinks_from_pdf()
        
        with open(self.pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            pillars = {
                'Operational Excellence': [],
                'Security': [],
                'Reliability': [],
                'Performance Efficiency': [],
                'Cost Optimization': [],
                'Sustainability': []
            }
            
            # PASS 1: Collect proper question IDs and their pillar mappings
            question_pillar_map = {}  # Maps (question_number, question_text_start) to pillar
            
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    # Look for proper question ID patterns (e.g., "SEC 7.How do you classify your data?")
                    proper_id_match = re.match(r'^(OPS|SEC|REL|PERF|COST|SUS)\s*(\d+)\.(.+)', line, re.IGNORECASE)
                    if proper_id_match:
                        pillar_abbrev = proper_id_match.group(1).upper()
                        q_num = int(proper_id_match.group(2))
                        q_text = proper_id_match.group(3).strip()
                        
                        # Map abbreviations to full pillar names
                        pillar_map = {
                            'OPS': 'Operational Excellence',
                            'SEC': 'Security',
                            'REL': 'Reliability',
                            'PERF': 'Performance Efficiency',
                            'COST': 'Cost Optimization',
                            'SUS': 'Sustainability'
                        }
                        pillar_name = pillar_map.get(pillar_abbrev, 'Unknown')
                        
                        # Use first few words of question as key to distinguish between pillars
                        question_key_words = ' '.join(q_text.lower().split()[:4])
                        composite_key = (q_num, question_key_words)
                        question_pillar_map[composite_key] = (pillar_name, pillar_abbrev)
            
            # PASS 2: Process actual questions using the pillar mappings
            current_pillar = None
            
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                lines = text.split('\n')
                
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    
                    # Initialize variables
                    q_num = None
                    q_text = None
                    j = i + 1
                    used_proper_id = False
                    
                    # Try to match question pattern
                    match = re.match(r'^(\d+)\.\s*(.+)', line)
                    if match:
                        q_num = int(match.group(1))
                        q_text = match.group(2)
                        
                        # Continue reading question if it spans multiple lines
                        while j < len(lines):
                            next_line = lines[j].strip()
                            if (next_line.startswith(('Selected', 'Not selected', 'Best Practices', 'High risk', 'Medium risk', 'Low risk', 'No improvements', 'Unanswered'))
                                or re.match(r'^\d+\.\s', next_line)):
                                break
                            if next_line and len(next_line) > 3 and next_line != 'Unanswered':
                                q_text += " " + next_line
                            j += 1
                        
                        # Clean question text
                        q_text = re.sub(r'\s*(Unanswered|Not Applicable)\s*$', '', q_text)
                        q_text = q_text.strip()
                        
                        # Use proper pillar mapping if available, otherwise fall back to content-based detection
                        question_key_words = ' '.join(q_text.lower().split()[:4])
                        composite_key = (q_num, question_key_words)
                        
                        if composite_key in question_pillar_map:
                            current_pillar, pillar_abbrev = question_pillar_map[composite_key]
                            used_proper_id = True
                        else:
                            # Fallback to old logic
                            if q_num <= 11 and current_pillar is None:
                                current_pillar = 'Operational Excellence'
                            elif 'securely operate' in q_text.lower() or 'security' in q_text.lower():
                                current_pillar = 'Security'
                            elif 'service quotas' in q_text.lower() or 'network topology' in q_text.lower():
                                current_pillar = 'Reliability'
                            elif 'appropriate cloud resources' in q_text.lower() or 'compute resources' in q_text.lower():
                                current_pillar = 'Performance Efficiency'
                            elif 'financial management' in q_text.lower() or 'cost' in q_text.lower():
                                current_pillar = 'Cost Optimization'
                            elif 'select Regions' in q_text.lower() or 'sustainability' in q_text.lower():
                                current_pillar = 'Sustainability'
                    
                    # If we found a question, process it
                    if q_num is not None and q_text is not None:
                        
                        # Extract all data (same as before)
                        selected_choices = []
                        not_selected_choices = []
                        na_choices = []
                        improvement_plans = []
                        notes = []
                        question_risk_level = ''
                        
                        # Process following lines
                        section = 'none'
                        
                        while j < len(lines) and not re.match(r'^\d+\.\s', lines[j].strip()):
                            next_line = lines[j].strip()
                            
                            # Check for risk levels
                            if 'High risk' in next_line:
                                question_risk_level = 'High Risk'
                            elif 'Medium risk' in next_line:
                                question_risk_level = 'Medium Risk'
                            elif 'Low risk' in next_line:
                                question_risk_level = 'Low Risk'
                            elif 'No improvements identified' in next_line:
                                question_risk_level = ''
                            
                            # Identify sections
                            if 'Selected choice(s)' in next_line:
                                section = 'selected'
                            elif 'Not selected choice(s)' in next_line:
                                section = 'not_selected'
                            elif 'Best Practices marked as Not Applicable' in next_line:
                                section = 'na'
                            elif 'Notes' in next_line and len(next_line) < 10:
                                section = 'notes'
                            elif 'Improvement plan' in next_line:
                                section = 'improvement'
                            elif next_line == '-' or next_line == 'Unanswered':
                                pass
                            elif next_line and len(next_line) > 5:
                                if ('© 2025, Amazon Web Services' in next_line or
                                    'Page' in next_line and 'of' in next_line or
                                    'Answer the question to view the improvement plan.' in next_line or
                                    'Ask an expert' in next_line):
                                    pass
                                elif section == 'selected' and not any(x in next_line for x in ['Selected', 'Not selected', 'Best Practices', 'Notes', 'Improvement']):
                                    selected_choices.append(next_line)
                                elif section == 'not_selected' and not any(x in next_line for x in ['Selected', 'Not selected', 'Best Practices', 'Notes', 'Improvement']):
                                    not_selected_choices.append(next_line)
                                elif section == 'na' and not any(x in next_line for x in ['Selected', 'Not selected', 'Best Practices', 'Notes', 'Improvement']):
                                    na_choices.append(next_line)
                                elif section == 'notes' and not any(x in next_line for x in ['Selected', 'Not selected', 'Best Practices', 'Improvement']):
                                    notes.append(next_line)
                                elif section == 'improvement':
                                    if ('Ask an expert' not in next_line and
                                        'Answer the question to view' not in next_line and
                                        '© 2025, Amazon Web Services' not in next_line and
                                        not re.match(r'.*Page \d+ of \d+', next_line) and
                                        'No risk detected for this question. No action needed' not in next_line and
                                        len(next_line) > 10):
                                        # Check if this line starts with capital letter (new item) or lowercase (continuation)
                                        if next_line[0].isupper() or not improvement_plans:
                                            improvement_plans.append(next_line)
                                        else:
                                            # Continuation of previous item
                                            if improvement_plans:
                                                improvement_plans[-1] += " " + next_line
                            
                            j += 1
                        
                        # Filter out "None of these" if other options exist
                        def filter_none_of_these(choices, other_choices_exist):
                            if other_choices_exist:
                                return [choice for choice in choices if 'None of these' not in choice]
                            return choices
                        
                        has_other_selected = any('None of these' not in choice for choice in selected_choices)
                        has_other_not_selected = any('None of these' not in choice for choice in not_selected_choices)
                        has_other_na = any('None of these' not in choice for choice in na_choices)
                        
                        if has_other_selected or has_other_not_selected or has_other_na:
                            selected_choices = filter_none_of_these(selected_choices, True)
                            not_selected_choices = filter_none_of_these(not_selected_choices, True)
                            na_choices = filter_none_of_these(na_choices, True)
                        
                        # Generate question ID - use proper abbreviation if available
                        if used_proper_id:
                            question_id = f"{pillar_abbrev}-{q_num:02d}"
                        else:
                            # Fallback to old abbreviation mapping
                            pillar_abbrev_map = {
                                'Operational Excellence': 'OPS',
                                'Security': 'SEC',
                                'Reliability': 'REL',
                                'Performance Efficiency': 'PERF',
                                'Cost Optimization': 'COST',
                                'Sustainability': 'SUS'
                            }
                            question_id = f"{pillar_abbrev_map.get(current_pillar, 'UNK')}-{q_num:02d}"
                        
                        # Clean improvement plans and get URLs for this page
                        clean_improvement_plans = []
                        page_urls = hyperlinks_by_page.get(page_num, [])
                        
                        for plan in improvement_plans:
                            clean_plan = re.sub(r'Ask an expert', '', plan)
                            clean_plan = re.sub(r'© \d+, Amazon Web Services.*?All rights reserved\.', '', clean_plan)
                            clean_plan = re.sub(r'Page \d+ of \d+', '', clean_plan)
                            clean_plan = clean_plan.strip()
                            if clean_plan and len(clean_plan) > 5:
                                clean_improvement_plans.append(clean_plan)
                        
                        improvement_text = '\n'.join(clean_improvement_plans) if clean_improvement_plans else ''
                        notes_text = '\n'.join(notes) if notes else ''
                        
                        # Determine overall risk (only show if there are not selected items)
                        overall_risk = question_risk_level if not_selected_choices else ''
                        
                        # Create question data structure
                        question_data = {
                            'question_id': question_id,
                            'pillar': current_pillar,
                            'question': q_text,
                            'risk_level': overall_risk,
                            'notes': notes_text,
                            'improvement_plan': improvement_text,
                            'choices': [],
                            'stats': {
                                'selected': len(selected_choices),
                                'not_selected': len(not_selected_choices),
                                'na': len(na_choices)
                            },
                            'improvement_items': []
                        }
                        
                        # Add all choices
                        for choice in selected_choices:
                            question_data['choices'].append({
                                'choice': choice,
                                'status': '✅ Selected'
                            })
                        
                        for choice in not_selected_choices:
                            question_data['choices'].append({
                                'choice': choice,
                                'status': '⚠️ Not Selected'
                            })
                        
                        for choice in na_choices:
                            question_data['choices'].append({
                                'choice': choice,
                                'status': 'Not Applicable'
                            })
                        
                        # Add improvement plan items with smart URL matching
                        for plan in clean_improvement_plans:
                            # Use smart matching to find the best URL for this specific improvement item
                            matched_url = self.match_improvement_item_to_url(plan, page_urls)
                            
                            question_data['improvement_items'].append({
                                'item': plan,
                                'url': matched_url
                            })
                        
                        # If no choices, add placeholder
                        if not question_data['choices']:
                            question_data['choices'].append({
                                'choice': 'Assessment not completed - no choices identified',
                                'status': '⚠️ Not Selected'
                            })
                            question_data['stats'] = {'selected': 0, 'not_selected': 1, 'na': 0}
                        
                        # Add to pillar
                        if current_pillar:
                            pillars[current_pillar].append(question_data)
                        
                        i = j - 1
                    else:
                        # No question pattern found, continue to next line
                        pass
                    
                    i += 1
        
        return pillars
    
    def get_workload_data(self):
        """Return standardized workload data structure"""
        
        workload_props = self.extract_workload_properties()
        pillars_data = self.extract_improvement_plan_with_smart_urls()
        
        return {
            'workload_properties': workload_props,
            'pillars': pillars_data,
            'source_type': 'pdf',
            'source_info': self.pdf_path
        }
