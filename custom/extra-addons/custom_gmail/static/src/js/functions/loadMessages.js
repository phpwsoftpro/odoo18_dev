/** @odoo-module **/

export async function loadMessages() {
    // Mock data with threads
    this.state.messages = [
        {
            id: 1,
            email_sender: "Tony Aasen",
            email: "tony.aasen@example.com",
            subject: "World map 🌎",
            preview: "Hi Robert, I think, but I really don't remember...",
            date_received: "Feb 20",
            gmail_body: `Hi again Robert,

I think, but I really don't remember if I asked you about it earlier, but we are looking for a map solution for our webpages, where we can tag/mark all KTV Working Drone partners all around the world.

Do you know about a fairly simple solution for a taggable map like this?`,
            unread: true,
            starred: false,
            thread_id: 'thread-1', // Add thread ID
            thread_count: 3 // Number of messages in thread
        },
        {
            id: 2,
            email_sender: "Hoàng Đức Tài",
            email: "taivip@gmail.com",
            subject: "Hâyyyyy",
            preview: "Hi Robert, I think, but I really don't remember...",
            date_received: "Feb 20",
            gmail_body: `Hi again Robert,

I think, but I really don't remember if I asked you about it earlier, but we are looking for a map solution for our webpages, where we can tag/mark all KTV Working Drone partners all around the world.

Do you know about a fairly simple solution for a taggable map like this?`,
            unread: true,
            starred: false,
            thread_id: 'thread-2',
            thread_count: 2
        },
    ];
    
    // Thread messages database
    this.state.threads = {
        'thread-1': [
            {
                id: 101,
                email_sender: "Robert Smith",
                email: "robert.smith@example.com",
                subject: "Re: World map 🌎",
                date_received: "Feb 18",
                gmail_body: `Hi Tony,

Have you considered using Google Maps API or Leaflet? Both offer pretty straightforward tagging functionality.

Best,
Robert`,
                unread: false,
                starred: false,
            },
            {
                id: 102,
                email_sender: "Tony Aasen",
                email: "tony.aasen@example.com",
                subject: "Re: World map 🌎",
                date_received: "Feb 19",
                gmail_body: `Thanks Robert,

I'll take a look at those options. Do you know if they're expensive for commercial use?

Regards,
Tony`,
                unread: false,
                starred: false,
            },
            {
                id: 1, // This is the main message from inbox
                email_sender: "Tony Aasen",
                email: "tony.aasen@example.com",
                subject: "Re: World map 🌎",
                date_received: "Feb 20",
                gmail_body: `Hi again Robert,

I think, but I really don't remember if I asked you about it earlier, but we are looking for a map solution for our webpages, where we can tag/mark all KTV Working Drone partners all around the world.

Do you know about a fairly simple solution for a taggable map like this?`,
                unread: true,
                starred: false,
            }
        ],
        'thread-2': [
            {
                id: 201,
                email_sender: "Robert Smith",
                email: "robert.smith@example.com",
                subject: "Re: Hâyyyyy",
                date_received: "Feb 19",
                gmail_body: `Hello Hoàng,

What can I help you with regarding this topic?

Best,
Robert`,
                unread: false,
                starred: false,
            },
            {
                id: 2, // This is the main message from inbox
                email_sender: "Hoàng Đức Tài",
                email: "taivip@gmail.com",
                subject: "Re: Hâyyyyy",
                date_received: "Feb 20",
                gmail_body: `Hi again Robert,

I think, but I really don't remember if I asked you about it earlier, but we are looking for a map solution for our webpages, where we can tag/mark all KTV Working Drone partners all around the world.

Do you know about a fairly simple solution for a taggable map like this?`,
                unread: true,
                starred: false,
            }
        ]
    };
    
    this.loadStarredState();
}